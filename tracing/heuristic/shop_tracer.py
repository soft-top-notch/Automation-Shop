import tracing.selenium_utils.common as common
from tracing.rl.environment import Environment


class IEnvActor:
    
    def get_states(self):
        """
        States for actor
        """
        raise NotImplementedError
    
    @abstractmethod
    def get_action(self, control):
        """
        Should return an action for every control
        """
        raise NotImplementedError

    @abstractmethod
    def get_state_after_action(self, action, control, environment):
        """
        Should return a new state or the old state
        Also should return wheather environmenet should discard last action
        """
        raise NotImplementedError


# ToDo List:
# 1. Copy the rest of orignial ShopTracer to this ShopTracer
# 2. Add method Discard to Environment (by storing stack of it's states (url, f_idx, c_idx))
# 3. Implement other actors 

class ShopTracer:
    
    ## .. Copy the rest from original ShopTracer and adopt
    def apply_actor(actor, state):
        while self.env.has_next_control():
            ctrl = self.env.get_next_control()
            action = actor.get_action(ctrl)
            
            env.apply_action(action)
            new_state, discard = actor.get_state_after_action(state, ctrl, action, self.env)
            
            # Discard last action
            if discard:
                self.env.discard()
                
            if new_state != state:
                return new_state
        
        return state
