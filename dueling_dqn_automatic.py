import cv2
import time
import torch
import torch.nn.functional as F
import numpy as np
import dueling_dqn_manual
from dueling_dqn import DQNAgent, SMALL_BATCH_SIZE
from tool_manager import ToolManager
from game_control import take_action, pause_game, restart
from grab_screen import grab, extract_self_and_boss_blood, extract_posture_bar


class GameEnvironment:
    def __init__(self, width=96, height=88, episodes=3000):
        self.width = width
        self.height = height
        self.episodes = episodes
        self.windows = {
            'self_blood': (58, 562, 398, 575),
            'boss_blood': (58, 92, 290, 108),
            'self_posture': (395, 535, 635, 552),
            'boss_posture': (315, 73, 710, 88)
        }
        self.paused = True
        self.manual = False
        self.debugged = False
        self.is_dead = False
        self.boss_has_extra_life = True
        self.boss_phase1_complete = False
        self.boss_phase2_complete = False
        self.self_stop_mark = 0
        self.boss_stop_mark = 0
        self.target_step = 0
        self.heal_count = 9

    def grab_screens(self):
        return {key: grab(window) for key, window in self.windows.items()}

    @staticmethod
    def extract_features(screens):
        self_blood, boss_blood = extract_self_and_boss_blood(
            screens['self_blood'], screens['boss_blood'])
        self_posture, boss_posture = extract_posture_bar(
            screens['self_posture'], screens['boss_posture'])
        return {'self_hp': self_blood, 'boss_hp': boss_blood,
                'self_posture': self_posture, 'boss_posture': boss_posture}

    def resize_screens(self, screens):
        resized_screens = {}
        for key, img in screens.items():
            img_tensor = torch.from_numpy(img).permute(2, 0, 1).unsqueeze(0).float().cuda()
            resized_img = F.interpolate(img_tensor, size=(self.width, self.height), mode='bilinear',
                                        align_corners=False)
            resized_screens[key] = resized_img.squeeze(0).permute(1, 2, 0).cpu().numpy()
        return resized_screens

    @staticmethod
    def merge_states(screens):
        return np.concatenate([img.transpose(2, 0, 1) for img in screens.values()], axis=0)

    def reset_marks(self):
        self.self_stop_mark = 0
        self.boss_stop_mark = 0
        self.target_step = 0
        self.is_dead = False


class GameAgent:
    def __init__(self, input_channels=12, action_space=9, model_file="./models"):
        self.dqn_agent = DQNAgent(input_channels, action_space, model_file)
        self.TRAIN_BATCH_SIZE = SMALL_BATCH_SIZE

    def choose_action(self, state):
        return self.dqn_agent.choose_action(state)

    def store_transition(self, *args):
        self.dqn_agent.store_transition(*args)

    def train(self, episode):
        self.dqn_agent.train(self.TRAIN_BATCH_SIZE, episode)

    def update_target_network(self):
        self.dqn_agent.update_target_network()

    def save_model(self, episode):
        self.dqn_agent.save_model(episode)


class GameState:
    def __init__(self, features):
        self.current = features
        self.next = {}

    def update(self, features):
        self.next = features


class GameController:
    def __init__(self):
        self.total_reward = 0
        self.env = GameEnvironment()
        self.agent = GameAgent()
        self.tool_manager = ToolManager()
        dueling_dqn_manual.start_listeners()

    def action_judge(self, state):
        if state.next['self_hp'] < 2:
            if not self.env.is_dead:
                reward, done = -10, 1
                self.total_reward += reward
                self.env.is_dead = True
                self.env.reset_marks()
                print(f'You are dead and get the reward: {reward:.2f}')
            else:
                reward, done = 0, 1
        elif state.next['boss_hp'] < 3:
            if self.env.boss_has_extra_life and not self.env.boss_phase1_complete:
                self.env.boss_has_extra_life = False
                reward, done = 30, 0
                print(f'You beat the first phase of the boss! Reward: {reward:.2f}')
                self.env.boss_phase1_complete = True
            elif not self.env.boss_has_extra_life and not self.env.boss_phase2_complete:
                reward, done = 40, 2
                self.env.reset_marks()
                self.total_reward += reward
                print(f'You finally beat the boss and get the reward: {reward:.2f}')
                self.env.boss_phase2_complete = True
            else:
                reward, done = 0, 0
        else:
            deltas = {key: state.next[key] - state.current[key] for key in state.current}
            reward = self.calculate_reward(deltas)
            done = 0
            self.total_reward += reward
            print(f'Current reward: {reward:.2f}, Total accumulated reward: {self.total_reward:.2f}')
        return reward, done

    def calculate_reward(self, deltas):
        reward = 0
        if deltas['self_hp'] <= -6 and self.env.self_stop_mark == 0:
            reward -= 3
            self.env.self_stop_mark = 1
        else:
            self.env.self_stop_mark = 0

        if deltas['boss_hp'] <= -3 and self.env.boss_stop_mark == 0:
            reward += 15
            self.env.boss_stop_mark = 1
        else:
            self.env.boss_stop_mark = 0

        if deltas['self_posture'] > 8:
            reward -= 2

        if deltas['boss_posture'] > 8:
            reward += 8

        return reward

    def run(self):
        grab_interval = 0.033
        tool_action_space_reduced = False
        heal_action_space_reduced = False
        for episode in range(self.env.episodes):
            self.env.reset_marks()
            print("Press 'T' to start the screen capture")
            self.env.paused = pause_game(self.env.paused)

            last_time, last_grab_time = time.time(), time.time()

            # Initial screen capture and feature extraction
            screens = self.env.grab_screens()
            features = self.env.extract_features(screens)
            state_obj = GameState(features)

            while True:
                if self.env.paused:
                    continue
                self.env.target_step += 1
                current_time = time.time()

                # Control screen capture frequency to optimize performance
                if current_time - last_grab_time >= grab_interval:
                    screens = self.env.grab_screens()
                    last_grab_time = current_time

                cv2.waitKey(1)
                # Process screen data and state
                resized_screens = self.env.resize_screens(screens)
                state = self.env.merge_states(resized_screens)
                print(f'------------------Processing time: {time.time() - last_time:.2f}s in episode {episode}------------------')
                last_time = time.time()

                # Action selection: manual or AI
                if self.tool_manager.tools_exhausted and not tool_action_space_reduced:
                    tool_action_space_reduced = True
                    self.agent.dqn_agent.action_space -= 3

                if self.env.heal_count == 0 and not heal_action_space_reduced:
                    heal_action_space_reduced = True
                    self.agent.dqn_agent.action_space -= 1

                action = self.get_manual_action() if self.env.manual else self.agent.choose_action(state)

                if not self.env.manual and action is not None:
                    take_action(action, self.env.debugged, self.tool_manager)

                # Get next state and update
                next_features, next_state = self.get_next_state(screens)
                state_obj.update(next_features)

                # Evaluate reward and done status
                reward, done = self.action_judge(state_obj)

                if action == 7:
                    self.env.heal_count -= 1
                    if state_obj.current['self_hp'] < 50:
                        reward += 5
                    else:
                        reward -= 3

                if action:
                    self.agent.store_transition(state, action, reward, next_state, done)

                # Train regularly
                if self.env.target_step % self.agent.TRAIN_BATCH_SIZE == 0:
                    self.agent.train(episode)

                # Handle game logic based on done status
                if done:
                    self.handle_done_state(done)
                    break

                # Pause control
                self.env.paused = pause_game(self.env.paused)
                state_obj.current = state_obj.next.copy()

            # Update and restart logic after each episode
            self.post_episode_updates(episode)

        cv2.destroyAllWindows()

    def handle_done_state(self, done):
        # Player death
        if done == 1:
            if not self.env.manual:
                restart(self.env.debugged, boss_defeated=False)
            else:
                while True:
                    screens = self.env.grab_screens()
                    features = self.env.extract_features(screens)
                    player_health = features['self_hp']
                    print(f"Checking for revival, Player Health: {player_health:.2f}%")
                    if player_health > 5:
                        print("Player has revived!")
                        break
        # Boss death
        elif done == 2:
            if not self.env.manual:
                restart(self.env.debugged, boss_defeated=True)
            else:
                print(f"The boss is dead and you can press the T if you are ready for the next boss")
                self.env.paused = True
                self.env.paused = pause_game(self.env.paused)

    @staticmethod
    def get_manual_action():
        if dueling_dqn_manual.keyboard_result is not None:
            action = dueling_dqn_manual.keyboard_result
            print(f'Keyboard action detected: {action}')
            dueling_dqn_manual.keyboard_result = None
            return action
        elif dueling_dqn_manual.mouse_result is not None:
            action = dueling_dqn_manual.mouse_result
            print(f'Mouse action detected: {action}')
            dueling_dqn_manual.mouse_result = None
            return action

    def get_next_state(self, screens):
        resized_screens = self.env.resize_screens(screens)
        next_state = self.env.merge_states(resized_screens)
        next_features = self.env.extract_features(screens)
        return next_features, next_state

    def post_episode_updates(self, episode):
        if episode % 10 == 0 and not self.env.debugged:
            self.agent.update_target_network()
        if episode % 5 == 0 and not self.env.debugged:
            self.agent.save_model(episode)


if __name__ == '__main__':
    GameController().run()
