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

    def get_label_not_equals(self):
        """Strings that can't be for control's label"""
        return []

    def get_label_not_contains(self):
        """Strings that can't be as substring of control's label"""
        return ['mail', 'search', 'name', 'country', 'state', 'card', 'zip', 'message', 'text', 'phone']


    def is_applicable(self, ctrl):
        if ctrl.type not in [Types.text, Types.select]:
            return False

        if ctrl.label:
            ctrl_label = ctrl.label.strip().lower()
            for not_equals in self.get_label_not_equals():
                if not_equals == ctrl_label:
                    return False

            for not_contains in self.get_label_not_contains():
                if not_contains in ctrl_label:
                    return False

        if ctrl.type == Types.select:
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
        return ['1', '01', '20']
    
    def __str__(self):
        return "InputBDay"

    def get_label_not_equals(self):
        return ["month", "year", "input month", "input year", "mm", "yyyy", "email", "input email"]


class InputBMonth(InputBirthday):
    def get_contains(self):
        return ['01', '1', 'January', 'Jan', 'january', 'jan']
    
    def get_not_contains(self):
        return ['13', '28', '31']

    def __str__(self):
        return "InputBMonth"

    def get_label_not_equals(self):
        return ["day", "year", "input day", "input year", "dd", "yyyy", "email", "input email"]


class InputBYear(InputBirthday):
    def get_contains(self):
        return ['1972', '72']

    def __str__(self):
        return "InputBYear"

    def get_label_not_equals(self):
        return ["day", "month", "input day", "input month", "dd", "mm", "email", "input email"]



class InputEmail(IAction):
    def is_applicable(self, ctrl):
        if ctrl.type != Types.text:
            return False

        ctrl_label = ctrl.label
        if not ctrl_label:
            return True

        ctrl_label = ctrl_label.strip().lower()
        if ctrl_label in ['dd', 'mm', 'yyyy', 'day', 'month', 'year', 'log in', 'login']:
            return False

        for not_contains in ['phone', 'search', 'first name', 'last name']:
            if not_contains in ctrl_label:
                return False

        return True

        
    def apply(self, ctrl, driver, user):
        if self.is_applicable(ctrl):
            email = user.get('email', 'test@gmail.com')

            enter_text(driver, ctrl.elem, email)
            time.sleep(1)

            return True
        
        return False
    
    def __str__(self):
        return "Input Email"


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
    actions = [InputBDay(), InputBMonth(), InputBYear(), Click(), InputEmail(), Nothing()]

