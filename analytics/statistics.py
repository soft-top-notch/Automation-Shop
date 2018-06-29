import os
import csv
import time
import random
from random import choice
from builtwith import builtwith
import requests
from requests.exceptions import ConnectionError


class Statistics:
	"""docstring for Statistics"""
	result = {}
	total_count = 100
	urls = []

	def __init__(self, result, file_url, user_agents=None, proxy=None):
		self.result = result
		self.user_agents = user_agents
		self.proxy = proxy
		self.urls = self.get_url_lists(file_url)

	def __random_agent(self):
		_user_agents = [
			'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/65.0.3325.181 Safari/537.36'
		]

		if self.user_agents and isinstance(self.user_agents, list):
			return choice(self.user_agents)
		return choice(_user_agents)

	def get_url_lists(self, file_url):
		urls = []

		if os.access(file_url, os.R_OK):
			with open(file_url, 'r') as f:
				reader = csv.reader(f)
				data_list = list(reader)
				for item in data_list:
					if not item[0].startswith('http://'):
						urls.append('http://' + item[0])
					else:
						urls.append(item[0])
			return random.sample(urls, self.total_count)

	def __request_url(self, url):
		try:
			response = requests.get(
				url,
				timeout=3,
			)
			response.raise_for_status()
		except requests.HTTPError as e:
			print('-----Error Request--------', e)
			return {'status': 800}
		except requests.ConnectionError as e:
			print('-----Error Request--------', e)
			return {'status': 800}
		except requests.ReadTimeout as e:
			print('-----Error Request--------', e)
			return {'status': 800}
		except requests.exceptions.SSLError as e:
			print('-----Error Request--------', e)
			return {'status': 800}
		except requests.exceptions.ChunkedEncodingError as e:
			print('-----Error Request--------', e)
			return {'status': 800}
		except requests.exceptions.ConnectTimeout as e:
			print('-----Error Request--------', e)
			return {'status': 800}
		else:
			return {'response': response, 'status': 200}

	def update_result(self, item):
		if item in self.result['first']:
			percent_num = self.result['second'][self.result['headToindex'][item]].split('%')[0]
			self.result['second'][self.result['headToindex'][item]] = str((float(percent_num) + 100 / self.total_count)) + '%'
		else:
			self.result['first'].append(item)
			self.result['second'].append(str(100 / self.total_count) + '%')
			if not self.result['headToindex']:
				self.result['headToindex'][item] = 0
			else:
				self.result['headToindex'][item] = self.result['headToindex'][self.result['first'][len(self.result['first'])-2]] + 1

	def get_result(self):
		try:
			print("---------urls---------------")
			print(self.urls)
			for url in self.urls:
				response = self.__request_url(url)
				if response['status'] != 200:
					continue
				print(response['response'])
				technologies = builtwith(url, response['response'].headers, response['response'].text, 'builtwith')
				print(technologies)
				if 'ecommerce' in technologies.keys():
					for item in technologies['ecommerce']:
						self.update_result(item)
				else:
					self.update_result('Unknown')
				print("--------url--------------")
				print(url)
				print("-------------")
				print(self.result)
			
		except Exception as e:
			print(e)
			pass

		return self.result

def main():
	result={
		'first': [],
		'second': [],
		'headToindex':{},
	}

	start_time = time.time()
	st = Statistics(result, 'pvio_vio_us_ca_uk_sample1.csv')
	result = st.get_result()

	print("Ended in "+ str(time.time() - start_time))

	with open('result.csv', 'w') as csvfile:
		try:
			writer = csv.writer(csvfile)
			list_res = []
			for item in result['first']:
				list_res.append([item.strip(), result['second'][result['headToindex'][item.strip()]].strip()])
				print(list_res)
			writer.writerows(list_res)
		except Exception as e:
			pass

if __name__ == "__main__":
	main()