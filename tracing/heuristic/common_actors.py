import tracing.selenium_utils.controls as controls
from tracing.rl.actions import *
import tracing.nlp


class ToProductPageLink(IEnvActor):
    contains = ['/product', '/commodity', '/drug', 'details', 'view']
    
    def get_states(self):
        return [States.new, States.shop]

    
    def get_action(self, control):
        if control.type != controls.Types.link:
            return Nothing()
        
        text = control.elem.get_attribute('outerHTML')
        if nlp.check_text(text, contains):
            return Click()
        else:
            return Nothing()
        
    
    def get_state_after_action(self, state, control, action, environment):
        if action == Nothing():
            return (state, False)
        
        if AddToCart.find_to_cart_elements(driver):
            return (States.product_page, False)
        
        # Discard last action
        return (state, True)
