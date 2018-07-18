import csv

class CheckoutUrlsInfo:
    """
        Save working urls
    """
    def __init__(self):
        self.list_urls = []
        self.filling_status = {}

    def save_urls(self, url, status=False):
        if url in self.list_urls:
            self.filling_status[url]=status
            return
        self.list_urls.append(url)
        self.filling_status[url]=status

    def write_csvfile(self, filepath, list_res):
        #Save result in csv file

        with open(filepath, 'w') as f:
            writer = csv.writer(f)
            writer.writerows(list_res)
            print("Successfully saved result!!!")

    def save_in_csv(self, filepath):
        save_list = []

        if self.list_urls:
            for url in self.list_urls:
                save_list.append([url])
        self.write_csvfile(filepath, save_list)

    def analyze_result(self):
        filepath="analyze_result.csv"

        self.save_in_csv(filepath)
        print("{} of {} checkout reachable urls are working to fill checkout fields".format(len(self.filling_status.keys()), len(self.list_urls)))