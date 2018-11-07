
class ITraceStatus:
    """
        Status of Shop Tracing
    """
    def __init__(self,
                 status,
                 message = None,
                 time_limit = 60,
                 state = None,
                 exception = None
                ):

        self.status = status
        self.message = message
        self.time_limit = time_limit
        self.state = state
        self.exception = exception,

    def __str__(self):
        if self.message:
            return 'Status: "{}"\n {}'.format(self.status, self.message)
        else:
            return 'Status: "{}"'.format(self.status)

    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, 
            sort_keys=True, indent=4)


class NotAvailable(ITraceStatus):
    """
        Status for shop that are not available
    """
    def __init__(self, message = None):
        super().__init__('Not Available', message = message)


class RequestError(ITraceStatus):
    """
        Get response with an error
    """
    def __init__(self, code, message = None):
        self.code = code
        super().__init__('Error {}'.format(self.code), message = message)
    
    def __str__(self):
        return 'Request Error, code: "{}"'.format(self.code)


class Timeout(ITraceStatus):
    """
        Request timed out
    """
    def __init__(self, time_limit, message = None):
        super().__init__("Timed Out", message = message, time_limit = time_limit)


    def toJSON(self):
        return json.dumps(self, default=lambda o: o.__dict__, 
            sort_keys=True, indent=4)


class ProcessingStatus(ITraceStatus):
    """
        Processing finished normal at some state
    """
    def __init__(self, state, exception = None, message = None):
        super().__init__('Finished at State',
                         state = state, 
                         exception = exception, 
                         message = message
                        )
        
    def __str__(self):
        return 'Finished at state: "{}"'.format(self.state)

