# PLEASE IMPORT ANY PACKAGES YOU NEED

# Builtins
from copy import copy
from functools import reduce
from random import choice
# HTN Planner package
from shop2.common import V
from shop2.conditions import AND
from shop2.conditions import Filter
from shop2.domain import Method
from shop2.domain import Task
from shop2.fact import Fact
from shop2.planner import FailedPlanException
from shop2.planner import planner
from shop2.planner import StopException
# Assignment helper code
from env_actions import env_actions
from move_planner import MovePlanner
from utils import create_fact_based_state
from shop2.conditions import NOT, OR
from shop2.conditions import Filter
import traceback

# from kbai_2024_hw4.helper_code.utils import create_fact_based_state
# from kbai_2024_hw4.helper_code.move_planner import MovePlanner
# from kbai_2024_hw4.helper_code.env_actions import env_actions


class DiceAdventureAgent:
    """
    Provides a uniform interface to connect agents to Dice Adventure environment.
    Developers must implement the take_action() function.
    - init():         Initialize any needed variables.
    - take_action():  Determines which action to take given a state (dict) and list of actions. Note that your
                      agent does not need to use the list of actions, it is just provided for convenience.
    """
    def __init__(self, character_name, character_id):
        """
        Initialize agent with character info and tracking variables
        """
        # Existing initialization
        self.character_name = character_name
        self.character_id = character_id
        self.htn_planner = None
        self.move_planner = MovePlanner()
        self.current_level = None
        self.shrine_reached = None
        
        # Tracking variables
        self.completed_levels = set()
        self.rounds_in_current_level = 0
        self._prev_shrine_reached = False
        
        # Debug mode - set to True for local testing, False for Gradescope
        self.DEBUG = True

    def debug_print(self, message):
        """Print message only if debug mode is enabled"""
        if self.DEBUG:
            print(message)

    def is_level_complete(self, state):
        scene = state['content']['scene']
        
        # 检查所有角色的神殿状态
        shrine_status = {'C11': False, 'C21': False, 'C31': False}
        shrine_positions = {}
        
        for obj in scene:
            if obj.get('entityType') == 'Shrine':
                character_id = obj.get('character')
                if character_id:
                    shrine_positions[character_id] = (obj.get('x'), obj.get('y'))
                    for char in scene:
                        if char.get('id') == character_id:
                            shrine_status[character_id] = (
                                char.get('x') == obj.get('x') and 
                                char.get('y') == obj.get('y')
                            )

        all_shrines_reached = all(shrine_status.values())

        # 检查塔状态
        tower_reached = False
        tower_pos = None
        for obj in scene:
            if obj.get('entityType') == 'Goal':
                tower_pos = (obj.get('x'), obj.get('y'))
                for char in scene:
                    if char.get('id') in shrine_status and \
                    (char.get('x'), char.get('y')) == tower_pos:
                        tower_reached = True
                        break
                break

        if self.rounds_in_current_level % 10 == 0:
            print(f"\nShrines status - Dwarf: {shrine_status['C11']}, "
                f"Giant: {shrine_status['C21']}, "
                f"Human: {shrine_status['C31']}")

        return all_shrines_reached and tower_reached

    def take_action(self, state):
        """
        Given a game state, the agent should determine which action to take and return an action.
        :param state: (dict) A 'Dice Adventure' game state 
        :return: (string) An action from the action set
        """
        try:
            # Update level tracking
            current_level = state['content']['gameData']['currLevel']
            if self.current_level != current_level:
                self.current_level = current_level
                self.shrine_reached = False
                self.rounds_in_current_level = 0
            else:
                self.rounds_in_current_level += 1

            # Collect player information
            player = find_player(state, self.character_id)
            if player is None:
                return 'wait'

            # Update shrine status
            if not self.shrine_reached:
                was_shrine_reached = self.shrine_reached
                self.shrine_reached = check_if_shrine_reached(state['content']['scene'], player)

            # Print periodic status (every 10 rounds)
            if self.rounds_in_current_level % 10 == 0:
                # 检查塔的状态
                tower_reached = False
                tower_pos = None
                for obj in state['content']['scene']:
                    if obj.get('entityType') == 'Goal':
                        tower_pos = (obj.get('x'), obj.get('y'))
                        # 检查是否有角色在塔的位置
                        for char in state['content']['scene']:
                            if char.get('id') in ['C11', 'C21', 'C31'] and \
                            (char.get('x'), char.get('y')) == tower_pos:
                                tower_reached = True
                                break
                        break

                # 检查所有角色的神殿状态
                shrine_status = {'C11': False, 'C21': False, 'C31': False}
                for obj in state['content']['scene']:
                    if obj.get('entityType') == 'Shrine':
                        character_id = obj.get('character')
                        if character_id:
                            for char in state['content']['scene']:
                                if char.get('id') == character_id:
                                    shrine_status[character_id] = (
                                        char.get('x') == obj.get('x') and 
                                        char.get('y') == obj.get('y')
                                    )

                print(f"\rLevel {current_level} | Round {self.rounds_in_current_level} | "
                    f"Phase: {state['content']['gameData']['currentPhase']} | "
                    f"Character: {self.character_name} | "
                    f"Position: ({player['x']}, {player['y']}) | "
                    f"Shrine reached: {self.shrine_reached} | "
                    f"All Shrines: {shrine_status['C11']},{shrine_status['C21']},{shrine_status['C31']} | "
                    f"Tower: {tower_reached}", end='')

            # Rest of the code remains the same but without debug prints
            fact_state = create_fact_based_state(state, self.shrine_reached, player)

            try:
                if self.htn_planner is None:
                    tasks = [[Task('play', )]]
                    self.htn_planner = planner(fact_state, tasks, self.get_domain())
                    action, args = self.htn_planner.send(None)
                    return action

                htn_operator, operator_grounded_args = self.htn_planner.send((True, fact_state))

                if htn_operator == 'random':
                    return choice(['up', 'down', 'left', 'right'])

                if htn_operator in ['wait', 'submit']:
                    return htn_operator

                if htn_operator == 'move':
                    try:
                        current_pos = (player['x'], player['y'])
                        
                        if operator_grounded_args and len(operator_grounded_args) >= 4:
                            target_pos = (operator_grounded_args[2], operator_grounded_args[3])
                        else:
                            unexplored = [(obj['x'], obj['y']) 
                                        for obj in state['content']['scene'] 
                                        if obj.get('sight_status') == 'unexplored']
                            if unexplored:
                                target_pos = min(unexplored, 
                                            key=lambda pos: abs(pos[0] - current_pos[0]) + 
                                                            abs(pos[1] - current_pos[1]))
                            else:
                                return 'wait'
                        
                        move_actions = self.move_planner.get_next_move(
                            src=current_pos,
                            dest=target_pos,
                            state=state
                        )
                        
                        if move_actions:
                            if state['content']['gameData']['currentPhase'] == 'Player_Planning':
                                num_actions = min(len(move_actions), player['actionPoints'])
                                return move_actions[:num_actions]
                            return move_actions[0]
                        
                        return 'wait'
                        
                    except Exception:
                        return 'wait'

                if htn_operator in ['pinga', 'pingb', 'pingc', 'pingd']:
                    if operator_grounded_args and len(operator_grounded_args) >= 2:
                        return htn_operator
                    return 'wait'

                return htn_operator

            except StopException:
                self.htn_planner = None
                return 'wait'
            
            except Exception:
                return 'wait'

        except Exception:
            return 'wait'
        
    def get_domain(self):
        """
        Implements an HTN domain consisting of tasks, methods, and operators.
        :return: (dict) An HTN domain containing methods for game strategy
        """
        domain_methods = {
            "play/0": [
                # Planning phase - focus on movement
                Method(
                    head=('play',),
                    preconditions=AND(
                        Fact(id='gameData', currentPhase='Player_Planning')
                    ),
                    subtasks=[
                        Task('navigate'),
                        Task('submit'),
                        Task('play')
                    ]
                ),
                # Pinning phase - focus on marking
                Method(
                    head=('play',),
                    preconditions=AND(
                        Fact(id='gameData', currentPhase='Player_Pinning')
                    ),
                    subtasks=[
                        Task('mark_objectives'),
                        Task('submit'),
                        Task('play')
                    ]
                ),
                # Default method
                Method(
                    head=('play',),
                    preconditions=(),
                    subtasks=[
                        Task('wait'),
                        Task('play')
                    ]
                )
            ],

            "navigate/0": [
                # If shrine not reached, move to shrine
                Method(
                    head=('navigate',),
                    preconditions=AND(
                        Fact(entityType='Shrine', character=self.character_id, reached=False),
                        Fact(entityType='Shrine', character=self.character_id, x=V('x'), y=V('y'))
                    ),
                    subtasks=[
                        Task('move', V('curr_x'), V('curr_y'), V('x'), V('y'))
                    ]
                ),
                # If shrine reached and tower visible, move to tower
                Method(
                    head=('navigate',),
                    preconditions=AND(
                        Fact(entityType='Shrine', character=self.character_id, reached=True),
                        Fact(entityType='Goal', x=V('x'), y=V('y'))
                    ),
                    subtasks=[
                        Task('move', V('curr_x'), V('curr_y'), V('x'), V('y'))
                    ]
                ),
                # Default exploration
                Method(
                    head=('navigate',),
                    preconditions=(),
                    subtasks=[
                        Task('explore')
                    ]
                )
            ],

            "mark_objectives/0": [
                # Mark shrine location
                Method(
                    head=('mark_objectives',),
                    preconditions=AND(
                        Fact(entityType='Shrine', character=self.character_id, reached=False),
                        Fact(entityType='Shrine', character=self.character_id, x=V('x'), y=V('y'))
                    ),
                    subtasks=[
                        Task('pingd', V('x'), V('y'))
                    ]
                ),
                # Mark dangerous areas
                Method(
                    head=('mark_objectives',),
                    preconditions=AND(
                        Fact(entityType='Monster', x=V('x'), y=V('y'))
                    ),
                    subtasks=[
                        Task('pinga', V('x'), V('y'))
                    ]
                ),
                # Default exploration mark
                Method(
                    head=('mark_objectives',),
                    preconditions=(),
                    subtasks=[
                        Task('pingb', V('curr_x'), V('curr_y'))
                    ]
                )
            ],

            "explore/0": [
                # Explore unexplored areas
                Method(
                    head=('explore',),
                    preconditions=(),
                    subtasks=[
                        Task('move', V('curr_x'), V('curr_y'), 
                            V('explore_x'), V('explore_y'))
                    ]
                ),
                # Default wait if no exploration needed
                Method(
                    head=('explore',),
                    preconditions=(),
                    subtasks=[
                        Task('wait')
                    ]
                )
            ]
        }

        domain = reduce(lambda x, y: {**x, **y}, [env_actions, domain_methods], {})
        return domain
    
def find_player(state, character_id):
    for obj in state['content']['scene']:
        if obj.get('id') == character_id:
            return copy(obj)


def check_if_shrine_reached(scene, player):
    shrine = None
    for obj in scene:
        if obj.get('character') == player['id']:
            shrine = obj
            break
    return shrine['x'] == player['x'] and shrine['y'] == player['y']


def get_player_position_cursor(x, y, action_plan):
    for action in action_plan:
        action = action.lower()
        if action == "up":
            y += 1
        elif action == "down":
            y -= 1
        elif action == "left":
            x -= 1
        elif action == "right":
            x += 1
        elif action == "wait":
            pass
    return x, y


def correct_position(coord, state):
    return coord if 0 <= coord < state['content']['gameData']['boardWidth'] else \
        (0 if coord < 0 else state['content']['gameData']['boardWidth']-1)







