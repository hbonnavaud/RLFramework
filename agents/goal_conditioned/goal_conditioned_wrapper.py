# Goal conditioned agent
from typing import Union

import numpy as np
from gym.spaces import Box, Discrete
import torch

from agents.goal_conditioned.goal_conditioned_agent import GoalConditionedAgent
from agents.value_based_agents.value_based_agent import ValueBasedAgent


class GoalConditionedWrapper(GoalConditionedAgent, ValueBasedAgent):
    """
    A wrapper that build a goal condition version of a given value based agent class.

    agent = GoalConditionedAgent(DQN, env.observation_space, env.action_space)  # replace DQN with any value based agent (DDPG, ...)
    agent.start_episode(observation, goal)
    goal_conditioned_action = agent.action()

    """

    def __init__(self, reinforcement_learning_agent_class, observation_space: Union[Box, Discrete],
                 action_space: Union[Box, Discrete], goal_from_observation_fun, **params):

        GoalConditionedAgent.__init__(self, observation_space, action_space, **params)

        self.reinforcement_learning_agent_class = reinforcement_learning_agent_class
        self.init_params["reinforcement_learning_agent_class"] = reinforcement_learning_agent_class
        self.init_params["goal_from_observation_fun"] = goal_from_observation_fun

        # Compute our agent new observation space as a goal-conditioned observation space (a concatenation of
        # our observation space and our goal space)

        self.get_goal_from_observation = goal_from_observation_fun
        if goal_from_observation_fun is None:
            self.get_goal_from_observation = lambda observation: observation.copy()

        self.reinforcement_learning_agent: ValueBasedAgent = \
            reinforcement_learning_agent_class(self.feature_space, action_space, **params)

        self.name = "Goal conditioned " + self.reinforcement_learning_agent.name

    def __getattr__(self, name):
        """Returns an attribute with ``name``, unless ``name`` starts with an underscore."""
        if name.startswith("_"):
            raise AttributeError(f"accessing private attribute '{name}' is prohibited")
        return getattr(self.reinforcement_learning_agent, name)

    def learn(self):
        self.reinforcement_learning_agent.learn()

    @property
    def feature_space(self):
        if isinstance(self.observation_space, Box) and isinstance(self.goal_space, Box):
            return Box(low=np.concatenate((self.observation_space.low, self.goal_space.low), 0),
                       high=np.concatenate((self.observation_space.high, self.goal_space.high), 0))
        elif isinstance(self.observation_space, Discrete) and isinstance(self.goal_space, Discrete):
            return Discrete(self.observation_space.n * self.goal_space.n)
        else:
            raise NotImplementedError("State space ang goal space with different types are not supported.")

    def get_features(self, observations, goals):
        # If observations are a batch and goal is a single one
        observations_batch_size = 1 if observations.shape == self.observation_space.shape else observations.shape[0]
        goals_batch_size = 1 if goals.shape == self.goal_space.shape else goals.shape[0]
        if observations_batch_size == 1 and goals_batch_size > 1:
            if observations.shape != self.observation_space.shape:
                observations = observations.squeeze()  # Remove batch
            observations = np.tile(observations, (goals_batch_size, *tuple(np.ones(len(observations.shape)).astype(int))))
        if goals_batch_size == 1 and observations_batch_size > 1:
            if goals.shape != self.goal_space.shape:
                goals = goals.squeeze()  # Remove batch
            goals = np.tile(goals, (observations_batch_size, *tuple(np.ones(len(goals.shape)).astype(int))))

        if isinstance(self.observation_space, Box) and isinstance(self.goal_space, Box):
            axis = int(observations_batch_size > 1 or goals_batch_size > 1)
            return np.concatenate((observations, goals), axis=int(observations_batch_size > 1 or goals_batch_size > 1))
        elif isinstance(self.observation_space, Discrete) and isinstance(self.goal_space, Discrete):
            return observations + goals * self.observation_space.n  # Use a bijection between N² and N
        else:
            raise NotImplementedError("State space ang goal space with different types are not supported.")

    def get_value(self, *information, actions=None):
        return self.reinforcement_learning_agent.get_value(self.get_features(*information), actions)

    def start_episode(self, *information, test_episode=False):
        super().start_episode(*information, test_episode=test_episode)
        self.reinforcement_learning_agent.start_episode(self.get_features(*information), test_episode)

    def action(self, observation, explore=True):
        wrapped_agent_observation = self.get_features(observation, self.current_goal)
        return self.reinforcement_learning_agent.action(wrapped_agent_observation, explore)

    def process_interaction(self, action, reward, new_observation, done, learn=True):
        super().process_interaction(action, reward, new_observation, done, learn=learn)
        new_observation = self.get_features(new_observation, self.current_goal)
        self.reinforcement_learning_agent.process_interaction(action, reward, new_observation, done, learn)

    def save_interaction(self, observation, action, reward, new_observation, done, goal=None):
        assert not self.under_test
        goal = self.current_goal if goal is None else goal
        observation = self.get_features(observation, goal)
        new_observation = self.get_features(new_observation, goal)
        self.reinforcement_learning_agent.save_interaction(observation, action, reward, new_observation, done)

    def get_estimated_distances(self, observations, goals):
        """
        Return the estimated distance between given goals and observations.
        """
        features = self.get_features(observations, goals)
        estimated_distance = self.reinforcement_learning_agent.get_value(features)
        if len(estimated_distance.shape) == 0:
            estimated_distance = estimated_distance.reshape((1,))
        estimated_distance = - estimated_distance.clip(float("-inf"), 0)
        return estimated_distance

    def set_device(self, device):
        self.reinforcement_learning_agent.set_device(device)
