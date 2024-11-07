import time
import pygetwindow as gw
from keys import input_keys


def take_action(action_index, debugged, tool_manager):
    if not debugged:
        if action_index == 0:
            input_keys.defense()
        elif action_index == 1:
            input_keys.attack()
        elif action_index == 2:
            input_keys.tiptoe()
        elif action_index == 3:
            input_keys.jump()
        # elif action_index in [4, 5, 6]:
        #     tool_manager.use_specific_tool(action_index - 4)


def wait_before_start(seconds, paused):
    action = "stopping" if paused else "starting"
    print(f"Waiting for {seconds} seconds before {action}...")
    time.sleep(seconds)
    print("Game paused." if paused else "Game started.")


def focus_game_window():
    windows = gw.getWindowsWithTitle('Sekiro')
    if windows:
        game_window = windows[0]
        game_window.activate()
    else:
        print("Game window not found")


def restart(env, defeated, defeat_count):
    def reset_actions_and_pause():
        pause_game(True)

    def restart_sequence():
        print("-------------------------Waiting for 7 seconds to restart the game-------------------------")
        time.sleep(5.5)
        focus_game_window()
        input_keys.lock_vision()
        time.sleep(0.5)
        input_keys.attack()
        time.sleep(1)

    if defeated == 1:
        if env.manual:
            print("-------------------------You are dead and should restart a new round in 4s-------------------------")
            time.sleep(4)
        else:
            restart_sequence()
    elif defeated == 2:
        print(f"-------------------------You beat the boss {defeat_count} times-------------------------")
        reset_actions_and_pause()


def pause_game(paused):
    while True:
        keys = input_keys.key_check()
        if 'P' in keys:
            paused = not paused
            print('Game paused' if paused else 'Game started')
            wait_before_start(3, paused)
        if paused:
            time.sleep(1)
        else:
            break

    return paused
