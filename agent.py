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
        Initialize any needed variables. The character_name and character_id arguments specify the name and ID
        of the character this agent will play as.
        :param character_name: (string) The character the agent will play as
        :param character_id: (string) The character ID corresponding to the character

        Player code index:
        {
            "Dwarf" : "C1",
            "Giant" : "C2",
            "Human" : "C3"
        }
        """
        self.character_name = character_name
        self.character_id = character_id
        self.htn_planner = None
        self.move_planner = MovePlanner()
        self.current_level = None
        self.shrine_reached = None

    def take_action(self, state):
        """
        Given a game state, the agent should determine which action to take and return an action.
        :param state: (dict) A 'Dice Adventure' game state
        :return: (string) An action from the action set
        """
        

        # Update current level if needed
        if self.current_level is None or self.current_level != state['content']['gameData']['currLevel']:
            self.current_level = state['content']['gameData']['currLevel']
            self.shrine_reached = False

        # Collect player information
        player = find_player(state, self.character_id)
        if not self.shrine_reached:
            self.shrine_reached = check_if_shrine_reached(state['content']['scene'], player)

        # Reformat state to form needed for planner
        fact_state = create_fact_based_state(state, self.shrine_reached, player)

        try:
            if self.htn_planner is None:
                tasks = [[Task('play', )]]
                self.htn_planner = planner(fact_state, tasks, self.get_domain())
                action, args = self.htn_planner.send(None)
                return action

            htn_operator, operator_grounded_args = self.htn_planner.send((True, fact_state))

            if htn_operator == 'random':
                return choice(['up', 'down', 'left', 'right', 'submit'])
            
            if htn_operator == 'wait':
                return 'wait'

            return htn_operator

        except StopException:
            # If planning fails, reinitialize the planner
            self.htn_planner = None
            return 'wait'
        except Exception as e:
            # If any other error occurs, return wait
            return 'wait'

    def get_domain(self):
        """
        Implements an HTN domain consisting of tasks, methods, and operators.
        :return: (dict) An HTN domain containing methods for game strategy
        """
        domain_methods = {
            "play/0": [
                # Pinning phase
                Method(
                    head=('play',),
                    preconditions=AND(
                        Fact(id='gameData', currentPhase='Player_Pinning')
                    ),
                    subtasks=[
                        Task('strategic_planning'),
                        Task('wait'),
                        Task('play')
                    ]
                ),
                # Planning phase
                Method(
                    head=('play',),
                    preconditions=AND(
                        Fact(id='gameData', currentPhase='Player_Planning')
                    ),
                    subtasks=[
                        Task('tactical_execution'),
                        Task('wait'),
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

            "strategic_planning/0": [
                # Random ping method
                Method(
                    head=('strategic_planning',),
                    preconditions=(),
                    subtasks=[
                        Task('random')
                    ]
                )
            ],

            "tactical_execution/0": [
                # Random movement method
                Method(
                    head=('tactical_execution',),
                    preconditions=(),
                    subtasks=[
                        Task('random')
                    ]
                )
            ]
        }

        # Merge with existing operators and return
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







