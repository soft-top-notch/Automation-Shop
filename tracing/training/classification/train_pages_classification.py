from tracing.rl.actions import *
from tracing.rl.a3cmodel import A3CModel
from tracing.rl.rewards import PopupRewardsCalculator
from tracing.rl.environment import Environment
from tracing.rl.actor_learner import ActionsMemory
from tracing.rl.actor_learner import ActorLearnerWorker

import tensorflow as tf
import tensorflow.contrib.slim as slim
import tensorflow.contrib.slim.nets as nets
import nets.inception_resnet_v2
from nets.inception_resnet_v2 import inception_resnet_v2_arg_scope

import threading
import csv, re
import random
import PIL

import numpy as np
import random
import sys

sys.path.append('..')
from popups.create_dataset import load_dataset as load_popup_dataset, read_small_image
from navigation.create_dataset import load_dataset as load_checkout_dataset


