# Goal conditioned agent
from random import randrange
import numpy as np
from .goal_conditioned_wrapper import GoalConditionedWrapper


class HER(GoalConditionedWrapper):
    """
    A global agent class for goal conditioned agents. The # NEW tag indicate differences between Agent class and this
    one.
    """

    def __init__(self,
                 reinforcement_learning_agent_class,
                 observation_space,
                 action_space,
                 goal_from_observation_fun,
                 **params):

        super().__init__(reinforcement_learning_agent_class, observation_space, action_space,
                         goal_from_observation_fun, **params)

        self.last_trajectory = []
        # ... and store relabelling parameters
        self.nb_resample_per_observations = 4
        self.name = self.reinforcement_learning_agent.name + " + HER"

    def start_episode(self, observation: np.ndarray, goal: np.ndarray, test_episode=False):
        self.last_trajectory = []
        return super().start_episode(observation, goal, test_episode)

    def process_interaction(self, action, new_observation, reward, done, learn=True):
        if learn and not self.under_test:
            self.last_trajectory.append((self.last_observation, action))
        super().process_interaction(action, new_observation, reward, done, learn=learn)

    def stop_episode(self):
        # Relabel last trajectory
        if self.under_test or len(self.last_trajectory) <= self.nb_resample_per_observations:
            return

        # For each observation seen :
        for observation_index, (observation, action) in enumerate(self.last_trajectory[:-self.nb_resample_per_observations]):
            new_observation_index = observation_index + 1
            new_observation, _ = self.last_trajectory[new_observation_index]

            # sample four goals in future observations
            for relabelling_id in range(self.nb_resample_per_observations):
                goal_index = randrange(new_observation_index, len(self.last_trajectory))
                target_observation, _ = self.last_trajectory[goal_index]
                goal = self.get_goal_from_observation(target_observation)

                features = self.get_features(observation, goal)
                # Compute a reward that goes from -1, for the first observation of the fake trajectory, to 0, if the
                # new_observation if the fake goal.
                reward = (new_observation_index / goal_index) - 1
                new_features = self.get_features(new_observation, goal)

                done = goal_index == new_observation_index
                self.reinforcement_learning_agent.save_interaction(features, action, reward, new_features, done)
        super().stop_episode()
