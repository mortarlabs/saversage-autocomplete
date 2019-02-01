from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.http import (HttpResponseBadRequest, HttpResponseForbidden,
                         JsonResponse)
from django.views.decorators.http import require_GET, require_POST
from django.core.cache import cache
from .trie import TrieNode
import sys
from datetime import datetime

def render_page(page):
    if getattr(page, 'specific', None):
        # For support of non-Page models like Snippets.
        page = page.specific
    if callable(getattr(page, 'autocomplete_label', None)):
        title = page.autocomplete_label()
    else:
        title = page.title
    return dict(id=page.id, title=title)


@require_GET
def objects(request):
    ids_param = request.GET.get('ids')
    if not ids_param:
        return HttpResponseBadRequest
    page_type = request.GET.get('type', 'wagtailcore.Page')
    try:
        model = apps.get_model(page_type)
    except Exception:
        return HttpResponseBadRequest

    try:
        ids = [
            int(id)
            for id in ids_param.split(',')
        ]
    except Exception:
        return HttpResponseBadRequest

    queryset = model.objects.filter(id__in=ids)
    if getattr(queryset, 'live', None):
        # Non-Page models like Snippets won't have a live/published status
        # and thus should not be filtered with a call to `live`.
        queryset = queryset.live()

    results = map(render_page, queryset)
    return JsonResponse(dict(items=list(results)))


def apply_filters(queryset, exclude):
    if getattr(queryset, 'live', None):
        # Non-Page models like Snippets won't have a live/published status
        # and thus should not be filtered with a call to `live`.
        queryset = queryset.live()

    try:
        exclusions = [int(item) for item in exclude.split(',')]
        queryset = queryset.exclude(pk__in=exclusions)
    except Exception:
        pass

class TrieNode():

    def __init__(self):
        self.nodes = {}
        self.item = None

    def set_node(self, key, item):
        if len(key) > 0:
            next_letter = key[:1]
            if not next_letter in self.nodes:
                self.nodes[next_letter] = TrieNode()
            #print("adding {}".format(next_letter))
            self.nodes[next_letter].set_node(key[1:], item)
        else:
            #print("  adding item")
            self.item = item

    def get_items(self, search):
        items = []

        if len(search) == 0:
            if self.item is not None:
                items.append(self.item)

            for letter in self.nodes.keys():
                #print("matching against {} ({})".format(letter, len(self.nodes[letter].nodes)))
                items.extend(self.nodes[letter].get_items(""))
        else:
            if search[:1] in self.nodes:
                items.extend(self.nodes[search[:1]].get_items(search[1:]))          

        return items      

    @staticmethod
    def build_trie(results):
        trie = TrieNode()
        for result in results:
            trie.set_node(result['title'].lower(), result)
        return trie     

def query_db(model, search_query, exclude):
    field_name = getattr(model, 'autocomplete_search_field', 'title')
    filter_kwargs = dict()
    filter_kwargs[field_name + '__icontains'] = search_query
    queryset = model.objects.filter(**filter_kwargs)
    
    apply_filters(queryset, exclude)

    return map(render_page, queryset[:20])

@require_GET
def search(request):
    start = datetime.now()
    search_query = request.GET.get('query', '')
    page_type = request.GET.get('type', 'wagtailcore.Page')
    try:
        model = apps.get_model(page_type)
    except Exception:
        return HttpResponseBadRequest

    cache_key = "{}_cached".format(page_type)
    cached_results = cache.get(cache_key)

    exclude = request.GET.get('exclude', '')
    if not cached_results:
        if len(search_query) == 0:
            # set the cache with this set
            queryset = model.objects.all()
            apply_filters(queryset, exclude)
            results = list(map(render_page, queryset))
            trie = TrieNode.build_trie(results)
            for letter in trie.nodes:
                cache.set("{}_{}".format(cache_key, letter), trie.nodes[letter], 60*60)
            cache.set(cache_key, True, 60*60)
            results = results[:20]
        else:
            results = query_db(model, search_query, exclude)
    else:
        first_letter = len(search_query[:1]) > 0 and search_query[:1] or "a"
        first_letter_cache = cache.get("{}_{}".format(cache_key, first_letter))
        if first_letter_cache:
            results =  first_letter_cache.get_items(search_query.lower()[1:])[:20]
        else:
            results = query_db(model, search_query, exclude)

    return JsonResponse(dict(items=list(results)))


@require_POST
def create(request, *args, **kwargs):
    value = request.POST.get('value', None)
    if not value:
        return HttpResponseBadRequest

    page_type = request.POST.get('type', 'wagtailcore.Page')
    try:
        model = apps.get_model(page_type)
    except Exception:
        return HttpResponseBadRequest

    content_type = ContentType.objects.get_for_model(model)
    permission_label = '{}.add_{}'.format(
        content_type.app_label,
        content_type.model
    )
    if not request.user.has_perm(permission_label):
        return HttpResponseForbidden

    method = getattr(model, 'autocomplete_create', None)
    if not callable(method):
        return HttpResponseBadRequest

    instance = method(value)
    return JsonResponse(render_page(instance))
