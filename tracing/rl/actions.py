from tracing.selenium_utils.controls import *
from abc import abstractmethod

class IAction:
    
    @abstractmethod
    def apply(self, control, driver, user):
        """
        Returns True or False if action was applied successfuly
        """
        raise NotImplementedError()


class InputBirthday(IAction):
    @abstractmethod
    def get_candidates(self):
        raise NotImplementedError()
    
    def apply(self, ctrl, driver, user):
        if ctrl.type not in [Types.text, Types.select]:
            return False
                
        if ctrl.type == Types.text:
            enter_text(driver, ctrl.elem, self.get_candidates()[0])
        else:
            val = None
            for txt in self.get_candidates():
                if txt in ctrl.values:
                    val = txt
                    
            if val is None:
                print('Not found values {} in control {}'.format(self.get_candidates(), ctrl))
                return False
            
            select_combobox_value(driver, ctrl.elem, val)
        
        return True
    
class InputBDay(InputBirthday):
    def get_candidates(self):
        return ['1', '01'] 
    
    def __str__(self):
        return "InputBDay"

    
class InputBMonth(InputBirthday):
    def get_candidates(self):
        return ['01', '1', 'January', 'Jan', 'january', 'jan']
    
    def __str__(self):
        return "InputBMonth"

    
class InputBYear(InputBirthday):
    def get_candidates(self):
        return ['1972', '72']

    def __str__(self):
        return "InputBYear"

    
class Click(IAction):
    def apply(self, ctrl, driver, user):
        if ctrl.type in [Types.radiobutton, Types.checkbox, Types.link, Types.button]:
            click(driver, ctrl.elem)
            return True
        
        return False
    
    def __str__(self):
        return "Click"

    
class Wait(IAction):
    def apply(self, ctrl, driver, user):
        time.sleep(2)
        return True
    
    def __str__(self):
        return "Wait"


class Nothing(IAction):
    def apply(self, ctrl, driver, user):
        return True
    
    def __str__(self):
        return "Do Nothing"


class Actions:
    actions = [InputBDay(), InputBMonth(), InputBYear(), Click(), Nothing()]

