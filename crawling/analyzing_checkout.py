import csv
import os

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

	def read_csvfile(self, filepath):
		'''Read CSV file contents as input data'''
		data_list = []

		if os.access(filepath, os.R_OK):
			with open(filepath, 'r') as f:
				reader = csv.reader(f)
				data_list = list(reader)
		return data_list

	def write_csvfile(self, filepath, list_res):
		'''Save result in csv file'''
		list_res = [["url", "should_fill", "filled_correct", "filled_incorrect"]] + list_res

		with open(filepath, 'w') as f:
			writer = csv.writer(f)
			writer.writerows(list_res)

	def save_in_csv(self, filepath, fill_added = False):
		checkout_reach_list = []
		checkout_fill_list = []

		if self.list_urls:
			for url in self.list_urls:
				if self.filling_status[url]:
					checkout_fill_list.append([url, 1, 1, 0])
					checkout_reach_list.append([url, 1, 1, 0])
				else:
					checkout_reach_list.append([url, 1, 0, 1])
		self.write_csvfile(filepath, checkout_reach_list)

		if fill_added:
			self.write_csvfile("fill_checkout.csv", checkout_fill_list)

	def analyze_result(self):
		filepath="analyze_result.csv"
		sum_should_correct = 0
		sum_should = 0
		sum_correct = 0
		sum_correct_incorrect = 0

		print("{} of {} checkout reachable urls are working to fill checkout fields".format(len(self.filling_status.keys()), len(self.list_urls)))
		lists = self.read_csvfile(filepath)

		for ind, line in enumerate(lists):
			if ind ==0:
				continue
			sum_should_correct += (int(line[1]) * int(line[2]))
			sum_should += int(line[1])
			sum_correct += int(line[2])
			sum_correct_incorrect += (int(line[2]) + int(line[3]))

		if not sum_should or not sum_correct_incorrect:
			print("recall = 0 and precision = 0")
		else:
			print("recall = {}".format(str(sum_should_correct / sum_should)))
			print("precision = {}".format(str(sum_correct / sum_correct_incorrect)))
