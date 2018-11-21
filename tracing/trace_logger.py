from abc import abstractmethod
from collections import namedtuple
import uuid
import os.path
import os
import json
import tempfile

from tracing.selenium_utils.common import *


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
    def create_img_file(self):
        fd, file_name = tempfile.mkstemp(suffix = '.png')
        file = os.fdopen(fd,'w')
        file.close()

        return file_name
    
    @abstractmethod
    def add_step(self, url, state, handler, screenshot_file, source, additional = None):
        raise NotImplementedError

    def save_snapshot(self, driver, state, handler, additional = None):
        
        if not hasattr(self, '_scale') or not self._scale:
            self._scale = get_scale(driver)
            
        url = get_url(driver)
        html = get_source(driver)
        
        screenshot_file = self.create_img_file()
        get_full_page_screenshot(driver, screenshot_file, self._scale, 10)

        self.add_step(url, state, handler, screenshot_file, html, additional)

        
class ITraceLogger:
    
    @abstractmethod
    def start_new(self, domain):
        raise NotImplementedError

    @abstractmethod
    def save(self, trace, status):
        raise NotImplementedError
    

Step = namedtuple('Step', ['url', 'state', 'handler', 'screen_path', 'source', 'additional'])


class FileTraceLogger(ITraceLogger):

    def __init__(self, results_file, img_folder, clear = True):
        
        self._results_file = results_file
        self._img_folder = img_folder
        
        # clear results file
        dirname = os.path.dirname(results_file)
        if not os.path.exists(dirname):
            os.makedirs(dirname)
        if clear:
            open(results_file, 'w+').close()
        
        # create image folder if not exists
        if not os.path.exists(img_folder):
            os.makedirs(img_folder)

        # Delete all .png files in directory
        if clear:
            old_files = [ f for f in os.listdir(img_folder) if f.endswith(".png") ]
            for file in old_files:
                os.remove(os.path.join(img_folder, file))


    @abstractmethod
    def start_new(self, domain):
        return FileTraceLogging(domain, self._img_folder)

    @abstractmethod
    def save(self, trace, status):
        """
        :param trace:    ITraceLogging - collected trace
        :param status:   ITraceStatus  - final status
        """
        trace.set_status(status)

        json = TraceEncoder().encode(trace)
        to_write = json + '\n'

        # Add json as one line to results file
        with open(self._results_file, "a") as f:
            f.write(to_write)
            f.flush()


class FileTraceLogging(ITraceLogging):

    def __init__(self, domain, img_folder):
        self.domain = domain
        self.steps = []
        self.status = None
        self._img_folder = img_folder
    
    def add_step(self, url, state, handler, screenshot_file, source, additional = None):
        file_name = str(uuid.uuid4()) + '.png'
        file_path = os.path.join(self._img_folder, file_name)
        os.rename(screenshot_file, file_path)

        step = Step(url, state, handler, file_path, source, additional)
        self.steps.append(step)

    def set_status(self, status):
        self.status = status



from mongoengine import *
import datetime
        
class MongoDbTraceLogger(ITraceLogger):

    @abstractmethod
    def start_new(self, domain):
        return MongoDbTrace(domain = domain, steps = [])

    @abstractmethod
    def save(self, trace, status):
        trace.final_state = status.state
        trace.status = str(status)
        
        trace.save()

class MongoDbStep(EmbeddedDocument):
    url = StringField()
    state = StringField()
    handler = StringField()
    screenshot = FileField()
    source = StringField()
    additional = StringField()
    
    added = DateTimeField(default=datetime.datetime.utcnow)

            
class MongoDbTrace(Document, ITraceLogging):
    domain = StringField(required=True)
    started = DateTimeField(default=datetime.datetime.utcnow)
    steps = ListField(EmbeddedDocumentField(MongoDbStep))
    
    final_state = StringField()
    status = StringField()
    
    def add_step(self, url, state, handler, screenshot_file, source, additional = None):
        step = MongoDbStep(url = url, 
                           state = state, 
                           handler = handler, 
                           source = source, 
                           additional = additional)
        
        with open(screenshot_file, 'rb') as image_file:
            step.screenshot.put(image_file, content_type='image/png')
        
        self.steps.append(step)
        os.remove(screenshot_file)


