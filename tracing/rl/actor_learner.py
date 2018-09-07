import random
import threading
from a3cmodel import A3CModel
from actions import *

class ActionsMemory:
    def __init__(self, gamma):
        self.imgs = []
        self.actions = []
        self.rewards = []
        self.gamma = gamma
    
    def append(self, img, action, reward):
        self.imgs.append(img)
        self.actions.append(action)
        self.rewards.append(reward)
    
    def to_input(self):
        
        sum_reward = 0
        rewards = []
        for i in range(len(self.imgs) - 1, -1, -1):
            sum_reward *= self.gamma
            sum_reward += self.rewards[i]
            rewards.append(sum_reward)
        
        return {
            "img": self.imgs,
            "actions": self.actions,
            "rewards": rewards
            }
        

class ActorLearnerWorker(threading.Thread):
    global_step = 0
    avg_reward = 0
    step_rewards = []
    
    def __init__(self, name, urls, global_model, env, max_steps = 1000):
        threading.Thread.__init__(self)
        
        self.name = name
        self.urls = urls
        self.session = global_model.session
        self.global_model = global_model
        self.local_model = A3CModel(global_model.num_actions, global_model = global_model, 
                                    session = self.session, name = self.name)
        self.env = env
        self.max_steps = max_steps
    
    def get_url(self):
        return random.choice(self.urls)
    
    def run(self):
        n_step = 5
        gamma = 0.99
        lr = 0.01
        entropy_l = 0.01
        
        with self.env:
            while ActorLearnerWorker.global_step < self.max_steps:
                ActorLearnerWorker.global_step += 1
                url = self.get_url()

                print('\n\nstarted url', 'http://' + url)
                self.env.start(url)

                controls = self.env.get_controls()
                print('extracted controls:', len(controls))
                # Popups specific, don't update window
                c_idx = 0
                sum_reward = 0

                while True:
                    memory = ActionsMemory(gamma = gamma)
                    # ToDo 1. Neat working with controls
                    # ToDo 2. Add scrolling?
                    while not self.env.is_final() and c_idx < len(controls):
                        ctrl = controls[c_idx]
                        if is_stale(ctrl.elem):
                            continue
                            
                        inp = self.env.get_control_as_input(ctrl)

                        print('control:', ctrl)
                        action_id = self.local_model.get_action(inp)
                        action = Actions.actions[action_id]
                        print('got action:', action)
                        
                        reward = self.env.apply_action(ctrl, action)
                        print('reward:', reward)

                        memory.append(inp, action_id, reward)

                        c_idx += 1
                        sum_reward += reward * (gamma ** self.env.step)
                        
                        if (self.env.step + 1) % n_step == 0:
                            break

                    self.local_model.train_from_memory(memory, dropout = 1.0 , lr = lr, er = entropy_l)

                    if self.env.is_final() or c_idx >= len(controls):
                        sum_reward += self.env.calc_final_reward() * (gamma ** self.env.step)
                        ActorLearnerWorker.avg_reward = ActorLearnerWorker.avg_reward * 0.99 + 0.01 * sum_reward
                        ActorLearnerWorker.step_rewards.append(sum_reward)
                        print(sum_reward)
                        break
