from tracing.selenium_utils.controls import *
from abc import abstractmethod

class IAction:
    
    @abstractmethod
    def apply(self, control, driver, user):
        """
        Returns True or False if action was applied successfuly
        """
        raise NotImplementedError()

    @abstractmethod
    def is_applicable(self, control):
        """
        Returns True or False whether the action could be applied to control
        """
        raise NotImplementedError()


class InputBirthday(IAction):
    @abstractmethod
    def get_contains(self):
        raise NotImplementedError()

    def get_not_contains(self):
        return []
    
    def is_applicable(self, ctrl):
        if ctrl.type not in [Types.text, Types.select]:
            return False
        
        if ctrl.type != Types.text:
            val = None
            for txt in self.get_contains():
                if txt in ctrl.values:
                    val = txt
                    
            if val is None:
                return False

            for txt in self.get_not_contains():
                if txt in ctrl.values:
                    return False

        return True
    
    def apply(self, ctrl, driver, user):
        if not self.is_applicable(ctrl):
            return False
                
        if ctrl.type == Types.text:
            enter_text(driver, ctrl.elem, self.get_contains()[0])
            time.sleep(1)

        else:
            val = None
            for txt in self.get_contains():
                if txt in ctrl.values:
                    val = txt

            if val is None:
                return False

            select_combobox_value(driver, ctrl.elem, val)
            time.sleep(1)

        return True
    
class InputBDay(InputBirthday):
    def get_contains(self):
        return ['1', '01'] 
    
    def __str__(self):
        return "InputBDay"

    
class InputBMonth(InputBirthday):
    def get_contains(self):
        return ['01', '1', 'January', 'Jan', 'january', 'jan']
    
    def get_not_contains(self):
        return ['13', '28', '31']

    def __str__(self):
        return "InputBMonth"

    
class InputBYear(InputBirthday):
    def get_contains(self):
        return ['1972', '72']

    def __str__(self):
        return "InputBYear"

    
class Click(IAction):
    
    def is_applicable(self, ctrl):
        return ctrl.type in [Types.radiobutton, Types.checkbox, Types.link, Types.button]
        
    def apply(self, ctrl, driver, user):
        if self.is_applicable(ctrl):
            click(driver, ctrl.elem)
            time.sleep(1)
            return True
        
        return False
    
    def __str__(self):
        return "Click"

    
class Wait(IAction):
    def is_applicable(self, ctrl):
        return True

    def apply(self, ctrl, driver, user):
        time.sleep(2)
        return True
    
    def __str__(self):
        return "Wait"


class Nothing(IAction):
    def is_applicable(self, ctrl):
        return True

    def apply(self, ctrl, driver, user):
        return True
    
    def __str__(self):
        return "Do Nothing"


class Actions:
    actions = [InputBDay(), InputBMonth(), InputBYear(), Click(), Nothing()]

