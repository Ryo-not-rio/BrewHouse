"""
This module deals with the inventory management.

It also deals with saving and loading of all the states of
the batches and tanks.

:attribute BEER_PROCESS:
A Process object that holds the list of Batch objects
by the stage of brewing it is in.
:attribute TANKS: List of all the Tank objects.
:attribute FERMENTERS:
List of Tank objects with fermentation capabilities.
:attribute CONDITIONERS:
List of Tank objects with conditioning capabilities.
"""
import os
import time
from datetime import time as t_time
from typing import Tuple, List
import logging
import _pickle

ABS_PATH = os.path.abspath(__file__)
D_NAME = os.path.dirname(ABS_PATH)
os.chdir(D_NAME)

LOGGER = logging.getLogger("inv_management")
LOGGER.setLevel(logging.DEBUG)
F_HANDLER = logging.FileHandler('log_file.log')
F_FORMAT = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
F_HANDLER.setFormatter(F_FORMAT)
LOGGER.addHandler(F_HANDLER)


class Process:
    """
    This class stores lists of Batch objects.

    Each batch object is stored in a list depending on which stage
    of the production it is in.
    """
    # pylint: disable=too-many-instance-attributes
    # pylint: disable=too-few-public-methods
    def __init__(self):
        """
        Initialises each list/dictionary.

        The dictionary steps allows each list to be accessed by its name.
        The list step_names allows the lists to be put in order.
        The dictionary finished stores each finished beer and its quantity.
        """
        LOGGER.debug("Initialising Process object")
        self.waiting = []
        self.brewing = []
        self.fermenting = []
        self.conditioning = []
        self.bottling = []
        self.finished = {}
        self.orders = []
        self.steps = {"waiting": self.waiting, "brewing": self.brewing,
                      "fermenting": self.fermenting, "conditioning": self.conditioning,
                      "bottling": self.bottling, "finished": self.finished}
        self.step_names = ["waiting", "brewing", "fermenting",
                           "conditioning", "bottling", "finished"]


class Tank:
    """This class is the class for each tank."""
    # pylint: disable=too-few-public-methods
    def __init__(self, name: str, volume: int, function: str):
        """
        Initialising the tank by setting its current batch to None.

        :param name: Name of the tank.
        :param volume: The maximum volume of tank.
        :param function:
        The capability of tank. 'fermenter', 'conditioner' or 'both'.
        """
        LOGGER.debug("Initialising Tank object")
        self.name = name
        self.volume = volume
        self.function = function
        self.current_batch = None


class Batch:
    """This class is the class for each batch."""
    # pylint: disable=too-few-public-methods
    def __init__(self, beer: str, volume: int):
        """
        Initialising the batch.
        :param beer: Name of the beer for the batch.
        :param volume: The volume for the batch.
        """
        LOGGER.debug("Initialising Batch object")
        self.beer = beer
        self.current_step = 0
        self.current_start_time = time.time()
        self.next_step = 1
        self.volume = volume
        self.current_tank = None

    def go_next_step(self, process_obj: Process, next_tank: str = None) -> int:
        """
        Handles all functions necessary for going to the next stage for the batch.

        :param process_obj: The Process object the batches and tanks are in.
        :param next_tank: The Tank to handle the next stage if any.

        :return: The current step of the Batch object.
        """
        LOGGER.info("Going to the next step")
        # Don't go to brewing stage if brewing equipment is occupied.
        if self.next_step == 1 and process_obj.brewing:
            return self.current_step

        # Removing self from previous stage
        if self.next_step <= 5:
            current_step_name = process_obj.step_names[self.current_step]
            process_obj.steps[current_step_name].remove(self)
            LOGGER.debug("Removed self from previous step")
            # Adding to the finished dictionary when finished.
            if self.next_step == 5:
                if self.beer in process_obj.finished.keys():
                    process_obj.finished[self.beer] += self.volume
                else:
                    process_obj.finished[self.beer] = self.volume
                LOGGER.debug("Added self to next step")
        # If it was in a tank, set tank as empty.
        if self.current_step in [2, 3]:
            self.current_tank.current_batch = None

        # If the next step requires a tank.
        if self.next_step in [2, 3]:
            if next_tank is not None:
                next_tank = find_tank_from_name(next_tank.split(" ")[0])
                if next_tank is not None:
                    next_tank.current_batch = self
                    self.current_tank = next_tank
                    self.current_step = self.next_step
                    self.next_step += 1
                else:
                    # If there are no available tanks set state to waiting.
                    LOGGER.warning("No tanks available")
                    self.current_step = 0
        else:
            self.current_step = self.next_step
            self.next_step += 1

        if self.current_step <= 4:
            next_step_name = process_obj.step_names[self.current_step]
            process_obj.steps[next_step_name].append(self)

        self.current_start_time = time.time()

        LOGGER.debug("Gone to next step")
        return self.current_step


def load_objects() -> Tuple[Process, List[Tank]]:
    """
    This module loads saved data.

    :return: The process object and the list of tanks.
    """
    LOGGER.info("Loading data")
    try:
        with open('process_object.dictionary', 'rb') as file:
            result = _pickle.load(file)
            process_obj = result[0]
            tanks = result[1]
        return process_obj, tanks

    except FileNotFoundError:
        LOGGER.error("File for objects not found")
        print("error: file not found")
        return False, False
    except EOFError:
        LOGGER.warning("Empty objects file. Creating new.")
        return False, False


def get_tank_types(tanks: List[Tank]) -> Tuple[List[Tank], List[Tank]]:
    """Making the list of fermenters and conditioners from the list of tanks"""
    LOGGER.debug("Sorting tanks by funciton")
    fermenters, conditioners = [], []
    for tank in tanks:
        if tank.function in ["both", "fermenter"]:
            fermenters.append(tank)
        if tank.function in ["both", "conditioner"]:
            conditioners.append(tank)

    return fermenters, conditioners


BEER_PROCESS, TANKS = load_objects()

# If file could not be loaded
if not BEER_PROCESS:
    LOGGER.warning("Couldn't load previous objects")
    BEER_PROCESS = Process()

# If tanks failed to be loaded from file.
if not TANKS:
    LOGGER.warning("Couldn't load previous tanks")
    TANKS = [Tank("Albert", 1000, "both"),
             Tank("Brigadier", 800, "both"),
             Tank("Camilla", 1000, "both"),
             Tank("Dylon", 800, "both"),
             Tank("Emily", 1000, "both"),
             Tank("Florence", 800, "both"),
             Tank("Gertrude", 680, "conditioner"),
             Tank("Harry", 680, "conditioner"),
             Tank("R2D2", 800, "fermenter")]

FERMENTERS, CONDITIONERS = get_tank_types(TANKS)


def show_beer_steps(process_obj=BEER_PROCESS) -> Tuple[List[Batch], List[str]]:
    """
    Returns list of batch of objects and strings describing each batch and its current stage.

    Looks through each step in the process object and returns
    list of all the batch objects found and a list of strings
    describing each batch.

    :param process_obj: The Process object containing each stage.

    :return: List of processing batches and a list describing each batch.
    """
    LOGGER.info("Making string for each batch")
    return_list = []
    object_list = []

    for key, step in process_obj.steps.items():
        if key != "finished":
            object_list += step
            for batch in step:
                ongoing_time = time.time()-batch.current_start_time
                minutes, seconds = divmod(ongoing_time, 60)
                hours, minutes = divmod(minutes, 60)
                days, hours = divmod(hours, 24)
                weeks, days = divmod(days, 7)
                # Creating the string for each batch
                return_list.append(str(batch.volume) + " Litres of " +
                                   batch.beer + " has been " + key
                                   + " for " + f"{weeks} weeks, {days} days and "
                                               f"{hours}:{minutes}:{int(seconds)}")

    return object_list, return_list


def show_tanks(tanks: List[Tank] = TANKS) -> List[str]:
    """
    Returns a list of string describing each occupied tank.

    :param tanks: List of all the tanks.
    :return: List containing description for each occupied tank.
    """
    LOGGER.info("Creating string for each tank")
    return_list = []
    for tank in tanks:
        if tank.current_batch is not None:
            batch = tank.current_batch
            return_list.append(tank.name + " is currently processing " +
                               str(batch.volume) + "L of " + batch.beer)

    return return_list


def add_batch(process_obj: Process = BEER_PROCESS, beer: str = "Organic Pilsner",
              volume: int = 1000) -> Batch:
    """
    Function for starting a new batch and creating a new batch object.

    If there is no brewing, the new batch starts brewing. If there is already a batch brewing,
    the new batch is put into the list of waiting beers.

    :param process_obj: The Process object containing the stages of production.
    :param beer: Name of beer for the batch.
    :param volume: Volume for the batch.

    :return: The batch object created.
    """
    LOGGER.info("Creating a new batch")
    batch = Batch(beer, volume)
    if not process_obj.brewing:
        batch.current_step = 1
        batch.next_step = 2
        process_obj.brewing.append(batch)
    else:
        LOGGER.warning("Batch added to waiting list")
        process_obj.waiting.append(batch)
    return batch


def available_tanks(volume: int, step: int) -> List[Tank]:
    """
    Gives all the available tanks for the given step and volume of batch.

    :param volume: Volume of batch.
    :param step: The step in the stage of production.

    :return: List of available tank objects.
    """
    LOGGER.info("Finding all available tanks")
    if step == 2:
        tank_list = FERMENTERS
    elif step == 3:
        tank_list = CONDITIONERS
    return_list = [tank for tank in tank_list
                   if volume <= tank.volume and tank.current_batch is None]
    return return_list


def find_tank_from_name(name: str) -> Tank:
    """Finds the tank object given its name"""
    for tank in TANKS:
        if tank.name == name:
            return tank
    return None


def process_done(batch_list: List[Batch], time_limit: t_time) -> List[Batch]:
    """Returns all batches that have been processing longer than the given time limit"""
    return_list = []
    for batch in batch_list:
        if time.time() - batch.current_start_time > time_limit:
            return_list.append(batch)
    return return_list


def finished_processes() -> List[Batch]:
    """
    Finds all batches that are finished done with its stage.

    All batches in all stages are looked at and compared with the
    required time for that stage. If the batch has been processing
    longer than that, it is returned.

    :return: List of batches finished with the stage.
    """
    LOGGER.info("Finding all the processes that are finished")
    done_waiting = []
    if not BEER_PROCESS.brewing:
        waits = [batch for batch in BEER_PROCESS.waiting if batch.next_step == 1]
        if waits:
            done_waiting.append(waits[0])

    done_brewing = process_done(BEER_PROCESS.brewing, 180*3600)
    done_fermenting = process_done(BEER_PROCESS.fermenting, 4*7*24*3600)
    done_conditioning = process_done(BEER_PROCESS.conditioning, 2*7*24*3600)
    done_bottling = [batch for batch in BEER_PROCESS.bottling
                     if time.time()-batch.current_start_time >= batch.volume*3600]

    return done_waiting + done_brewing + done_fermenting + done_conditioning + done_bottling


def save_objects(process_obj: Process, tanks_list: List[Tank]) -> str:
    """Saves the process object and list of tanks."""
    LOGGER.info("Saving objects")
    try:
        with open('process_object.dictionary', 'wb') as file:
            _pickle.dump([process_obj, tanks_list], file)
            return "success"
    except FileNotFoundError:
        LOGGER.error("Objects file not found")
        return "File not found"


if __name__ == "__main__":
    save_objects(BEER_PROCESS, TANKS)
