from abc import abstractmethod
from selenium_utils.common import *
from collections import namedtuple
import uuid
import os.path
import os
import json


class TraceEncoder(json.JSONEncoder):
    
    def default(self, o):
        if isinstance(o, tuple) and hasattr(o, '_asdict'):
            obj_dict = o._asdict()
        elif hasattr(o, '__dict__'):
            obj_dict = o.__dict__
        elif isinstance(o, list):
            return [self.default(item) for item in o]
        else:
            return o
        
        result = {}
        for key, value in obj_dict.items():
            if key.startswith('_'):
                continue
                
            value = self.default(value)
            result[key] = value

        return result

    
class ITraceLogging:
    """
    Object that logs current trace
    """
    @abstractmethod
    def add_step(self, url, state, handler, screenshot, source, additional = None):
        raise NotImplementedError

    def save_snapshot(self, driver, state, handler, additional = None):
        url = driver.current_url
        html = driver.page_source
        screenshot = get_screenshot(driver)

        self.add_step(url, state, handler, screenshot, html, additional)

        
class ITraceLogger:
    
    @abstractmethod
    def start_new(self, domain):
        raise NotImplementedError

    @abstractmethod
    def save(self, trace, status):
        raise NotImplementedError
    

Step = namedtuple('Step', ['url', 'state', 'handler', 'screen_path', 'source', 'additional'])


class FileTraceLogger(ITraceLogger):

    def __init__(self, results_file, img_folder):
        
        self._results_file = results_file
        self._img_folder = img_folder
        
        # clear results file
        open(self._results_file, 'w').close()
        
        # create image folder if not exists
        if not os.path.exists(img_folder):
            os.makedirs(img_folder)

        # Delete all .png files in directory
        old_files = [ f for f in os.listdir(img_folder) if f.endswith(".png") ]
        for file in old_files:
            os.remove(os.path.join(img_folder, file))


    @abstractmethod
    def start_new(self, domain):
        return FileTraceLogging(domain, self._img_folder)

    @abstractmethod
    def save(self, trace, status):
        trace.set_status(status)
        
        # Add json as one line to results file
        with open(self._results_file, "a") as f:
            json = TraceEncoder().encode(trace)
            f.write(json)
            f.write('\n')


class FileTraceLogging(ITraceLogging):

    def __init__(self, domain, img_folder):
        self.domain = domain
        self.steps = []
        self.status = None
        self._img_folder = img_folder
    
    def add_step(self, url, state, handler, screenshot, source, additional = None):
        file_name = str(uuid.uuid4()) + '.png'
        file_path = os.path.join(self._img_folder, file_name)
        with open(file_path, "wb") as file:
            file.write(screenshot)

        step = Step(url, state, handler, file_path, source, additional)
        self.steps.append(step)

    def set_status(self, status):
        self.status = status

