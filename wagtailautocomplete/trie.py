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
            trie.set_node(result['title'], result )
        return trie     

def main():
    results = [{"title": "cat"}, {"title": "catching"}, {"title": "cattery"}]
    trie = TrieNode.build_trie(results)
    
    for result in trie.get_items("catt"):
        print(result['title'])

if __name__ == "__main__":
    main()
