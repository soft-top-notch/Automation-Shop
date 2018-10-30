import random
import threading
from tracing.rl.a3cmodel import A3CModel
from tracing.rl.actions import *
import traceback


class ActionsMemory:
    def __init__(self, gamma, prev_action, is_prev_applied):
        self.imgs = []
        self.actions = []
        self.is_action_applied = []

        self.rewards = []
        self.gamma = gamma

        self.prev_action = prev_action
        self.is_prev_applied = is_prev_applied

        self.final_score = 0
        self.possible_actions = []

    
    def set_final_score(self, score):
        self.final_score = score


    def size(self):
        return len(self.imgs)


    @staticmethod
    def get_possible_actions(ctrl):
        possible_actions = []
        for a_id, action in enumerate(Actions.actions[:-1]):
            is_applicable = 1 if action.is_applicable(ctrl) else 0
            possible_actions.append(is_applicable)
        
        return possible_actions        


    def append(self, img, action, is_applied, reward, ctrl):
        self.imgs.append(img)
        self.actions.append(action)
        self.is_action_applied.append(1 if is_applied else 0)

        self.rewards.append(reward)

        possible_actions = ActionsMemory.get_possible_actions(ctrl)
        self.possible_actions.append(possible_actions)
    

    def to_input(self):
        batch_size = len(self.imgs)
        rewards = [0] * batch_size

        sum_reward = self.final_score
        for i in range(len(self.imgs) - 1, -1, -1):
            sum_reward *= self.gamma
            sum_reward += self.rewards[i]
            rewards[i] = sum_reward            
        
        return {
            "img": self.imgs,
            "actions": self.actions,
            "is_applied": self.is_action_applied,
            "rewards": rewards,
            "possible_actions": self.possible_actions
            }
        

class ActorLearnerWorker(threading.Thread):
    global_step = 0
    global_cv_step = 0
    avg_reward = 0
    step_rewards = []
    cv_losses = []

    # Start Url -> List of Tuples (list of memories, reward)
    best_examples = {}
    
    def __init__(self, name, urls, 
                         global_model, 
                         env, 
                         max_steps = 1000, 
                         lr = 0.01, 
                         n_step = 5, 
                         entropy_l = 0.01, 
                         gamma = 0.99, 
                         dropout = 0.5,
                         l2 = 0.01,
                         steps_lr_decay = 20 # Number of steps after which learning rate should decay
                ):
        threading.Thread.__init__(self)
        
        self.name = name
        self.urls = urls
        self.session = global_model.session
        self.global_model = global_model
        #self.local_model = A3CModel(global_model.num_actions, global_model = global_model, 
        #                            session = self.session, name = self.name)
        
        self.local_model = global_model        
        
        self.env = env
        self.max_steps = max_steps

        self.n_step = n_step
        self.gamma = gamma
        self.lr = lr
        
        self.entropy_l = entropy_l
        self.dropout = dropout
        self.l2 = l2
        self.steps_lr_decay = steps_lr_decay
    

    def get_url(self):
        return random.choice(self.urls)
    

    def on_finished(self, url, memories, reward):
        last_best = ActorLearnerWorker.best_examples.get(url, [])
        ActorLearnerWorker.best_examples[url] = last_best

        better = list(filter(lambda pair: pair[1] > reward + 0.5, last_best))
        if len(better) > 0:
             print('training from best of {}'.format(url))
             for i in range(3):
                 example = random.choice(better)
                 for memory in example[0]:
                     losses = self.local_model.train_from_memory(memory, 
                                                                 dropout = self.dropout, 
                                                                 lr = self.get_lr(), 
                                                                 er = self.entropy_l,
                                                                 l2 = self.l2
                                                                )
             
             return
        
        if len(last_best) >= 10:
            del last_best[0]
        
        last_best.append((memories, reward))
    
    
    def get_lr(self):
        step = ActorLearnerWorker.global_step // self.steps_lr_decay
        return self.lr * 1.0 / (1 + step)
    
    
    def act(self, url):
        sum_reward = 0

        if not self.env.start(url):
            return None

        lstm_state = None
        action_id = len(Actions.actions) - 1
        while not self.env.is_final() and self.env.has_next_controls():
            print('control:', str(ctrl)[:100])
            ctrl = self.env.get_next_control()
            inp = self.env.get_control_as_input(ctrl)

            pa = ActionsMemory.get_possible_actions(ctrl)

            action_id, to_apply, lstm_state = self.local_model.get_action(inp, pa, action_id, lstm_state, True)

            action = Actions.actions[action_id]
            print('got action: {}, is_applying: {}'.format(action, to_apply))

            if to_apply:
                reward = self.env.apply_action(ctrl, action)            
                sum_reward += reward * (self.gamma ** self.env.step)
                print('reward:', reward)

        v_score = self.env.calc_final_reward()
        sum_reward += v_score * (self.gamma ** self.env.step)

        return sum_reward


    def act_and_learn(self, url):
        sum_reward = 0
        memories = []
        lstm_state = None
        state_to_train = None

        action_id = len(Actions.actions) - 1
        to_apply = False
        while True:
            memory = ActionsMemory(self.gamma, action_id, to_apply)
            memories.append(memory)
            
            while not self.env.is_final() and self.env.has_next_control():
                ctrl = self.env.get_next_control()
                inp = self.env.get_control_as_input(ctrl)

                print('control:', str(ctrl)[:100])
                pa = ActionsMemory.get_possible_actions(ctrl)
                action_id, to_apply, lstm_state = self.local_model.get_action(inp, pa, action_id, lstm_state, True)

                action = Actions.actions[action_id]
 
                print('got action: {}, is_applying: {}'.format(action, to_apply))

                if to_apply:
                    reward = self.env.apply_action(ctrl, action)
                    print('reward:', reward)
                else:
                    reward = 0
                
                memory.append(inp, action_id, to_apply, reward, ctrl)
                sum_reward += reward * (self.gamma ** self.env.step)
                
                if memory.size() % self.n_step == 0:
                    break             

            is_final = self.env.is_final() or not self.env.has_next_control()

            if is_final:
                v_score = self.env.calc_final_reward()
            else:
                # Find next element
                ctrl = self.env.get_next_control(move=False)
                inp = self.env.get_control_as_input(ctrl)

                v_score = self.local_model.estimate_score(inp, action_id, lstm_state) * self.gamma

            memory.set_final_score(v_score)
            
            losses = self.local_model.train_from_memory(memory, 
                                                                dropout = self.dropout, 
                                                                lr = self.get_lr(),
                                                                er = self.entropy_l,
                                                                l2 = self.l2,
                                                                lstm_state = state_to_train
                                                               )
            state_to_train = lstm_state
            print('policy_loss: {}, value_loss: {}, entropy_loss: {}'.format(losses[0], losses[1], losses[2]))
                    
            if is_final:
                sum_reward += v_score * (self.gamma ** self.env.step)
                ActorLearnerWorker.avg_reward = ActorLearnerWorker.avg_reward * 0.99 + 0.01 * sum_reward
                ActorLearnerWorker.step_rewards.append(sum_reward)
                self.on_finished(url, memories, sum_reward)
                print('sum_reward for {} is {}'.format(url, sum_reward))
                return sum_reward

        print('sum_reward for {} is {} how we entered here?'.format(url, sum_reward))        
        return sum_reward
                

    def run(self):        
        with self.env:
            while ActorLearnerWorker.global_step < self.max_steps:
                ActorLearnerWorker.global_step += 1
                url = self.get_url()

                print('\n\nstarted url', 'http://' + url)
                if not self.env.start(url):
                    continue
                
                try:
                    self.act_and_learn(url)
                except:
                    print('exception during processing url: {}'.format(url))
                    traceback.print_exc()
