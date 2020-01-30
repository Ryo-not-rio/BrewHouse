"""
This module is the main module. It deals with all of the user interface.

The layout of the interface was created using PyQt5 designer.

Form implementation generated from reading ui file 'interface.ui'.
Created by: PyQt5 UI code generator 5.13.0.
"""
import sys
from os import path as os_path, chdir
from math import ceil
from threading import Thread
from datetime import datetime, timedelta
from typing import Tuple, List, Dict, Callable, Union
from time import sleep as time_sleep
import logging
from PyQt5 import QtCore, QtGui, QtWidgets
import pyqtgraph as pg
from sales_predictions import plot_next_year, get_total
from inventory_management import Tank, Batch, \
    BEER_PROCESS, TANKS, show_beer_steps, show_tanks, add_batch, \
    available_tanks, finished_processes, save_objects
from read_file import write_data

LOGGER = logging.getLogger("user_interface")
LOGGER.setLevel(logging.DEBUG)
F_HANDLER = logging.FileHandler('log_file.log')
F_FORMAT = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
F_HANDLER.setFormatter(F_FORMAT)
LOGGER.addHandler(F_HANDLER)

ABS_PATH = os_path.abspath(__file__)
D_NAME = os_path.dirname(ABS_PATH)
chdir(D_NAME)


# pylint: disable=c-extension-no-member
def current_datetime() -> datetime:
    """Returning today's date as a datetime object."""
    return datetime.combine(datetime.today().date(), datetime.min.time())


def beer_suggestion() -> Tuple[str, int]:
    """
    Making a recommendation on the next batch to brew.

    The recommendation algorithm is as follows:
    1. Look at the 6 week period 10 weeks from now.
    2. For all the predicted demands, subtract the volumes
    currently waiting, brewing and fermenting.
    3. Get the beer with the highest demand after step 2.
    4. Look to see if any batches are brewing or waiting.
    5. If the result from step 4 is None, recommend the beer from step 3.

    :return: The name and suggested volume for the next beer to be brewed.
    """
    LOGGER.info("Calculating next batch suggestion")
    if plot_next_year()[0]:
        totals_dict = get_total(current_datetime() + timedelta(weeks=10), 7 * 6, plot_next_year())
        for batch in BEER_PROCESS.waiting + BEER_PROCESS.brewing + BEER_PROCESS.fermenting:
            LOGGER.info("There are batches waiting, brewing or fermenting")
            totals_dict[batch.beer] -= batch.volume * 2

        maximum = max(totals_dict.values())
        key = list(totals_dict.keys())[list(totals_dict.values()).index(maximum)]
        LOGGER.debug("Beer with max demand fetched")

        volume = int(ceil((maximum * 0.5) / 10.0)) * 10

        tanks = available_tanks(800, 2)
        if tanks and not BEER_PROCESS.brewing and \
                not [batch for batch in BEER_PROCESS.waiting if batch.next_step == 1]:
            max_possible = max([tank.volume for tank in tanks])
            volume = min(max_possible, volume)
            LOGGER.info("There is a beer suggestion")
            return key, volume
    LOGGER.info("No beer suggestion")
    return None, None


def get_next_tanks(batch_object: Batch) -> List[Tank]:
    """
    Returns the list of tanks that may be required for the next stage for a batch.

    :param batch_object: The Batch object to look tanks for.
    :return: List of tanks required if any.
    """
    LOGGER.info("Getting the list of tanks for next step")
    if batch_object.next_step in [2, 3]:
        LOGGER.info("Tanks are required for next step of %s", batch_object.beer)
        tanks = available_tanks(batch_object.volume, batch_object.next_step)
        if batch_object.current_tank is not None and\
                batch_object.current_tank.function == "conditioner":
            LOGGER.debug("Adding current tank to list.")
            tanks = [batch_object.current_tank] + tanks
        if tanks:
            LOGGER.info("Tanks returned")
            return tanks
    LOGGER.info("No tank required")
    return False


def save_continuously():
    """Procedure to save the state of batches and tanks every 2 minutes"""
    while True:
        save_objects(BEER_PROCESS, TANKS)
        LOGGER.warning("Current state auto-saved")
        time_sleep(120)


def pop_up(text: str):
    """Shows a pop up box for the given text"""
    message = QtWidgets.QMessageBox()
    message.setText(text)
    message.exec_()


class UiMainWindow:
    """This class is for creating the user interface"""
    # pylint: disable=too-many-instance-attributes
    def get_graph(self, dates: List[datetime] = None,
                  data: Dict[str, List[int]] = None, symbol: str = None):
        """
        This function plots the graph.

        A part of the graph can be plotted if the dates and data for
        it is given. The symbol for the data points can be changed.

        :param dates: List of dates when plotting part of graph.
        :param data: List of sales for each beer when plotting part of graph.
        :param symbol: Symbol for data points.
        """
        LOGGER.info("Getting graph")
        self.widget.clear()
        if self.widget.plotItem.legend:
            LOGGER.debug("Legend cleared")
            self.widget.plotItem.legend.scene().removeItem(self.widget.plotItem.legend)
        self.widget.setTitle("Prediction")

        if not dates or not data or len(dates) != len(data['Organic Pilsner']):
            start_date = current_datetime()
            dates, predict_dict = plot_next_year(start_date=start_date, date_range=180)
        else:
            predict_dict = data

        # Date in strings to show on graph
        string_dates = [date.strftime("%d/%m/%y") for date in dates]

        # Changing dates to integer so graph can be plotted.
        dates = [round((date.timestamp()-dates[0].timestamp())/(3600*24)) for date in dates]

        colours = ['r', 'g', 'b']
        self.widget.addLegend(size=(70, 50), offset=(10, 1))
        plots = []
        LOGGER.debug("Starting to plot")
        for counter, (key, beer) in enumerate(predict_dict.items()):
            colour = colours[counter]
            # Showing the total for the region the graph shows.
            plots.append(self.widget.plotItem.plot(dates, beer,
                                                   pen=pg.mkPen(colour, width=1),
                                                   name=key + ", " + str(int(sum(beer))) + " btls",
                                                   symbol=symbol))
        LOGGER.info("Graph plotted")
        # Adjusting ticks
        x_axis = self.widget.getAxis('bottom')
        x_axis.setTicks([list(zip(dates[::18], string_dates[::18]))])
        x_axis.setTickSpacing([(20, 0), (1, 0), (0.25, 0)])

    def show_tanks(self):
        """Showing tank states for each tank that is processing a batch."""
        LOGGER.info("Showing each tank state")
        self.tanks_list.clear()
        tank_strings = show_tanks()
        self.tanks_list.addItems(tank_strings)

    def make_step_function(self, batch: Batch, combo_box: QtWidgets.QComboBox = None) -> Callable:
        """Making the function to be linked for the next step button."""
        def go_next_step():
            """The function to be linked to the 'next step' button."""
            # If next step requires a tank.
            LOGGER.info("next step button clicked")
            if combo_box is None:
                batch.go_next_step(BEER_PROCESS)
            else:
                batch.go_next_step(BEER_PROCESS, combo_box.currentText())
            self.refresh_page()

        return go_next_step

    def make_add_function(self, name: str, volume: str) -> Callable:
        """Making the function to connect to the button to add a batch."""
        LOGGER.info("Making function to connect to add batch button")

        def add_batch2():
            """The function to add a batch"""
            LOGGER.info("Add batch button clicked")
            add_batch(beer=name, volume=volume)
            self.refresh_page()
        return add_batch2

    def show_beers(self):
        """
        Showing all batches that is currently being processed.

        Each batch that is being processed and its description is found
        using show_beer_steps and a button to go to the next step and a
        combo box if necessary is created.
        """
        LOGGER.info("Showing each processing batch to interface")
        self.batches_list.clear()

        # Getting each Batch object and the description.
        batch_objects, beers = show_beer_steps()
        for counter, beer in enumerate(beers):
            batch_object = batch_objects[counter]
            add_item = QtGui.QListWidgetItem(beer)
            add_item.setFlags(add_item.flags() ^ QtCore.Qt.ItemIsSelectable)
            self.batches_list.addItem(add_item)

            # Layout for button and combo box.
            widget = QtWidgets.QWidget(self.batches_list)
            layout = QtWidgets.QHBoxLayout(widget)
            layout.setContentsMargins(230, 20, 0, 0)

            LOGGER.debug("Getting next function")
            next_function = self.make_step_function(batch_object)
            get_next = get_next_tanks(batch_object)

            # If the next step requires a tank, create combo box.
            if get_next:
                tanks = get_next
                combo_box = QtWidgets.QComboBox(widget)
                layout.addWidget(combo_box)
                for tank in tanks:
                    combo_box.addItem(tank.name + " " + str(tank.volume) + "L")
                next_function = self.make_step_function(batch_object, combo_box)
            LOGGER.info("Next function retrieved")

            # Making the button to go to the next step.
            button = QtWidgets.QToolButton(widget)
            button.setText("Next Step")
            button.clicked.connect(next_function)

            layout.addStretch()
            layout.addWidget(button)

            self.batches_list.setItemWidget(add_item, widget)
        LOGGER.debug("Beers shown")

    def refresh_page(self):
        """Function to update all descriptions in the interface"""
        LOGGER.info("Refreshing page")
        self.show_beers()
        self.show_tanks()
        self.show_bottled()
        self.show_orders()
        self.get_recommendation()
        save_objects(BEER_PROCESS, TANKS)

    def add_beers(self):
        """
        This is the function to add batches.

        The volume and beer name is obtained from the interface
        and passed to add_batch.
        """
        LOGGER.info("Adding a new batch")
        volume = self.volume_edit.toPlainText()
        try:
            volume = int(volume)
        except ValueError:
            LOGGER.error("Integer not entered for volume")
            pop_up("Please enter an integer")
        else:
            if volume != "" and 0 < volume <= 1000:
                beer = self.combo_box.currentText()
                add_batch(beer=beer, volume=volume)
                self.refresh_page()
            else:
                LOGGER.warning("Value between 0 and 1000 not entered for volume")
                pop_up("Please enter a value between 0 and 1000")

        self.volume_edit.setText("")

    def search_graph(self):
        """
        This is the function to search the graph

        Date and width is grabbed from the user interface
        which is then passed to plot_next_year to obtain the
        data. Next, get_graph is used to plot the graph.
        """
        LOGGER.info("Grabbing graph")
        # Grabbing the date and region from the interface
        date = self.date_edit.date().toPyDate()
        width = self.range_choice.currentText()

        # Changing date object to a datetime object
        date_time = datetime.combine(date, datetime.min.time())

        if width == "Week":
            d_range = 7
        else:
            d_range = 30

        # Getting the dates and data for specified region.
        dates, data = plot_next_year(start_date=date_time, date_range=d_range)
        if dates:
            self.get_graph(dates, data, "d")
        else:
            LOGGER.error("Date not found")
            pop_up("Failed to find date")

    def make_start_suggestion(self):
        """
        Make suggestions to start a new batch.

        If starting a new brew is suggested, the recommendation
        is shown and a button next to it to actually start the brew.
        """
        LOGGER.info("Showing the suggestions for batches to start")
        self.suggestions_list.clear()

        # Getting the suggestion
        key, volume = beer_suggestion()

        widget = QtWidgets.QWidget(self.suggestions_list)

        # If it is suggested to start a batch.
        if key is not None:
            LOGGER.debug("There is a suggestions")
            if volume > 10:
                # Creating the string to display.
                add_item = QtGui.QListWidgetItem("Start brewing " + str(volume) + "L of " + key)
                add_item.setFlags(add_item.flags() ^ QtCore.Qt.ItemIsSelectable)
                self.suggestions_list.addItem(add_item)

                # Creating the button
                button = QtWidgets.QToolButton(widget)
                button.setText("Execute")
                next_function = self.make_add_function(key, volume)
                button.clicked.connect(next_function)

                layout = QtWidgets.QHBoxLayout(widget)
                layout.setContentsMargins(0, 0, 0, 0)

                layout.addStretch()
                layout.addWidget(button)

                self.suggestions_list.setItemWidget(add_item, widget)
                LOGGER.debug("Suggestion shown")

    def make_next_suggestion(self):
        """
        This is the function to make a suggestion for batches that should be moved to the next step.

        It gets the batches that have finished in their process from finished_processes
        and displays it. If the next step doesn't require a tank, a button is displayed
        to actually move it to the next step.
        """
        LOGGER.info("Showing suggestion for batches to advance")
        step_finished = finished_processes()
        for batch in step_finished:
            add_item = QtGui.QListWidgetItem("Process next step for " + batch.beer + " that is "
                                             + BEER_PROCESS.step_names[batch.current_step] + "\n")
            add_item.setFlags(add_item.flags() ^ QtCore.Qt.ItemIsSelectable)
            self.suggestions_list.addItem(add_item)

            widget = QtWidgets.QWidget(self.suggestions_list)
            layout = QtWidgets.QHBoxLayout(widget)
            layout.setContentsMargins(0, 20, 0, 0)
            layout.addStretch()

            get_next = get_next_tanks(batch)
            # If a tank is not required in the next step
            if not get_next:
                LOGGER.debug("Next step does not requires a tank.")
                # Getting the function to link to the button.
                next_function = self.make_step_function(batch)

                # Making the button.
                button = QtWidgets.QToolButton(widget)
                button.setText("Execute")
                button.clicked.connect(next_function)
                layout.addWidget(button)

            self.suggestions_list.setItemWidget(add_item, widget)
        LOGGER.debug("Suggestions shown")

    def get_recommendation(self):
        """This shows the recommendations on the interface"""
        LOGGER.info("Retrieving recommendations")
        self.make_start_suggestion()
        self.make_next_suggestion()

    def show_bottled(self):
        """This shows all the bottled beers."""
        LOGGER.info("Showing bottled beers")
        self.bottled_list.clear()
        for beer, volume in BEER_PROCESS.finished.items():
            self.bottled_list.addItem(str(int(volume/0.5)) + " bottles of " + beer)

    def add_order(self):
        """
        Adding orders.

        The name, quantity and due date is retrieved from the interface
        and added to the orders list in the Process object.
        """
        LOGGER.info("Adding order")
        beer = self.combo_box_3.currentText()
        bottle_quantity = self.spin_box.value()
        due_date = self.date_edit_2.date().toPyDate()
        if bottle_quantity > 0:
            BEER_PROCESS.orders.append([beer, bottle_quantity, due_date])
            LOGGER.debug("Order added")
        else:
            pop_up("Please enter a value larger than 0")
        self.refresh_page()

    def make_deliver_button(self, order: List[Union[str, int]]) -> Callable:
        """
        Makes the function for the 'deliver' button for orders to be connected to.

        :param order: The list of attributes of an order.

        :return: The function for the 'deliver' button to be linked to.
        """
        LOGGER.info("Making function to link to deliver button")

        def deliver_order():
            """
            The function that is executed when the 'deliver' button is pressed.

            The order is removed from BEER_PROCESS, the number of bottles is
            updated if there is enough in the inventory.
            """
            LOGGER.info("Deliver button clicked")
            if order[0] in BEER_PROCESS.finished and \
                    BEER_PROCESS.finished[order[0]] >= order[1]*0.5:
                BEER_PROCESS.orders.remove(order)
                BEER_PROCESS.finished[order[0]] -= order[1]*0.5
                self.refresh_page()
                LOGGER.info("Order removed successfully")
            else:
                LOGGER.warning("Not enough inventory")
                pop_up("Not enough inventory")

        return deliver_order

    def show_orders(self):
        """
        Shows all the orders.

        For each order, the order displayed and a button to deliver the
        order is created.
        """
        LOGGER.info("Showing all orders")
        self.orders_list.clear()
        self.spin_box.setValue(1)

        # Retrieving the orders
        orders = BEER_PROCESS.orders
        for order in orders:
            # Making the string to show.
            add_item = QtGui.QListWidgetItem(str(order[1]) + " bottles of " + order[0]
                                             + " due " + order[2].strftime("%d/%m/%Y"))
            add_item.setFlags(add_item.flags() ^ QtCore.Qt.ItemIsSelectable)
            self.orders_list.addItem(add_item)

            next_function = self.make_deliver_button(order)
            LOGGER.debug("Next function retrieved")

            widget = QtWidgets.QWidget(self.orders_list)

            # Creating the button.
            button = QtWidgets.QToolButton(widget)
            button.setText("Deliver")
            button.clicked.connect(next_function)

            layout = QtWidgets.QHBoxLayout(widget)
            layout.setContentsMargins(0, 0, 0, 0)

            layout.addStretch()
            layout.addWidget(button)

            self.orders_list.setItemWidget(add_item, widget)
        LOGGER.debug("All orders shown")

    def add_file(self):
        """
        Adding a csv file to the existing file.

        File adding attempt is made and a message is shown in a pop up box.
        """
        LOGGER.info("Adding file")
        file_dir = self.file_dir_edit.text()
        self.file_dir_edit.setText("Enter file directory for new csv file")
        result = write_data(file_dir)
        if result == "success":
            message_text = "Successfully added csv file"
        else:
            LOGGER.error("Failed to add file")
            message_text = str(result)
        pop_up(message_text)

    # pylint: disable=too-many-statements
    def __init__(self, main_window: QtWidgets.QMainWindow):
        """
        This is the layout of each object in the user interface.

        :param main_window: QtMainWindow object.
        """
        main_window.setObjectName("main_window")
        main_window.resize(1751, 869)
        self.central_widget = QtWidgets.QWidget(main_window)

        font = QtGui.QFont()
        font.setPointSize(9)
        font.setUnderline(True)
        font2 = QtGui.QFont()
        font2.setPointSize(9)
        font2.setUnderline(False)

        self.date_edit = QtWidgets.QDateEdit(self.central_widget)
        self.date_edit.setGeometry(QtCore.QRect(160, 10, 110, 22))
        self.date_edit.setDateTime(QtCore.QDateTime.currentDateTime())
        self.search_label = QtWidgets.QLabel(self.central_widget)
        self.search_label.setGeometry(QtCore.QRect(105, 10, 55, 16))
        self.search_label.setText("Search:")
        self.search_label.setFont(font)
        self.range_choice = QtWidgets.QComboBox(self.central_widget)
        self.range_choice.setGeometry(QtCore.QRect(275, 10, 73, 22))
        self.range_choice.addItem("Week")
        self.range_choice.addItem("Month")
        self.search_button = QtWidgets.QPushButton(self.central_widget)
        self.search_button.setGeometry(QtCore.QRect(352, 7, 91, 26))
        self.search_button.setText("Search")
        self.search_button.clicked.connect(self.search_graph)
        self.graph_button = QtWidgets.QPushButton(self.central_widget)
        self.graph_button.setGeometry(QtCore.QRect(0, 5, 93, 28))
        self.graph_button.setText("Full Graph")
        self.graph_button.clicked.connect(self.get_graph)

        self.beer_label = QtWidgets.QLabel(self.central_widget)
        self.beer_label.setGeometry(QtCore.QRect(280, 760, 55, 16))
        self.beer_label.setObjectName("beer_label")
        self.beer_label.setText("Beer:")
        self.beer_label.setFont(font2)
        self.volume_label = QtWidgets.QLabel(self.central_widget)
        self.volume_label.setGeometry(QtCore.QRect(450, 760, 55, 16))
        self.volume_label.setObjectName("volume_label")
        self.volume_label.setText("Volume:")
        self.volume_label.setFont(font2)

        self.volume_edit = QtWidgets.QTextEdit(self.central_widget)
        self.volume_edit.setGeometry(QtCore.QRect(450, 780, 161, 31))
        self.volume_edit.setObjectName("volume_edit")

        self.combo_box = QtWidgets.QComboBox(self.central_widget)
        self.combo_box.setGeometry(QtCore.QRect(280, 780, 170, 31))
        self.combo_box.setObjectName("combo_box")
        self.combo_box.addItem("Organic Red Helles")
        self.combo_box.addItem("Organic Pilsner")
        self.combo_box.addItem("Organic Dunkel")

        self.batch_button = QtWidgets.QPushButton(self.central_widget)
        self.batch_button.setGeometry(QtCore.QRect(360, 810, 90, 28))
        self.batch_button.setObjectName("batch_button")
        self.batch_button.setText("Add Batch")
        self.batch_button.clicked.connect(self.add_beers)
        self.refresh_button = QtWidgets.QPushButton(self.central_widget)
        self.refresh_button.setGeometry(QtCore.QRect(450, 810, 90, 28))
        self.refresh_button.setObjectName("refresh_button")
        self.refresh_button.setText("Refresh")
        self.refresh_button.clicked.connect(self.refresh_page)

        self.widget = pg.PlotWidget(self.central_widget)
        self.widget.setGeometry(QtCore.QRect(0, 40, 901, 421))
        self.widget.setObjectName("widget")
        self.get_graph()

        self.batches_list = QtWidgets.QListWidget(self.central_widget)
        self.batches_list.setGeometry(QtCore.QRect(0, 485, 450, 276))
        self.batches_list.setObjectName("batches_list")
        self.batches_list.setWordWrap(True)
        self.tanks_list = QtWidgets.QListWidget(self.central_widget)
        self.tanks_list.setGeometry(QtCore.QRect(450, 485, 450, 276))
        self.tanks_list.setObjectName("tanks_list")
        self.tanks_list.setWordWrap(True)
        self.batch_label = QtWidgets.QLabel(self.central_widget)
        self.batch_label.setGeometry(QtCore.QRect(5, 465, 86, 16))
        self.batch_label.setText("Batch Status:")
        self.batch_label.setFont(font)
        self.tank_label = QtWidgets.QLabel(self.central_widget)
        self.tank_label.setGeometry(QtCore.QRect(460, 465, 90, 16))
        self.tank_label.setText("Tank Status:")
        self.tank_label.setFont(font)

        self.suggestions_list = QtWidgets.QListWidget(self.central_widget)
        self.suggestions_list.setGeometry(QtCore.QRect(900, 40, 426, 721))
        self.suggestions_list.setWordWrap(True)
        self.suggest_label = QtWidgets.QLabel(self.central_widget)
        self.suggest_label.setGeometry(QtCore.QRect(904, 10, 120, 21))
        self.suggest_label.setText("Suggested To Do:")
        self.suggest_label.setFont(font)
        self.get_recommendation()

        self.order_button = QtWidgets.QPushButton(self.central_widget)
        self.order_button.setGeometry(QtCore.QRect(1493, 80, 93, 28))
        self.order_button.setText("Add Order")
        self.order_button.clicked.connect(self.add_order)
        self.date_edit_2 = QtWidgets.QDateEdit(self.central_widget)
        self.date_edit_2.setGeometry(QtCore.QRect(1613, 40, 111, 31))
        self.date_edit_2.setDateTime(QtCore.QDateTime.currentDateTime())
        self.spin_box = QtWidgets.QSpinBox(self.central_widget)
        self.spin_box.setGeometry(QtCore.QRect(1513, 40, 46, 31))
        self.spin_box.setRange(1, 1000)
        self.combo_box_3 = QtWidgets.QComboBox(self.central_widget)
        self.combo_box_3.setGeometry(QtCore.QRect(1358, 40, 146, 31))
        self.combo_box_3.addItem("Organic Red Helles")
        self.combo_box_3.addItem("Organic Pilsner")
        self.combo_box_3.addItem("Organic Dunkel")
        self.beer_type_label = QtWidgets.QLabel(self.central_widget)
        self.beer_type_label.setGeometry(QtCore.QRect(1358, 18, 76, 21))
        self.beer_type_label.setFont(font2)
        self.beer_type_label.setText("Beer Type:")
        self.due_label = QtWidgets.QLabel(self.central_widget)
        self.due_label.setGeometry(QtCore.QRect(1613, 20, 55, 16))
        self.due_label.setFont(font2)
        self.due_label.setText("Due:")
        self.bottles_label = QtWidgets.QLabel(self.central_widget)
        self.bottles_label.setGeometry(QtCore.QRect(1561, 50, 46, 16))
        self.bottles_label.setFont(font2)
        self.bottles_label.setText("bottles")

        self.orders_list = QtWidgets.QListWidget(self.central_widget)
        self.orders_list.setGeometry(QtCore.QRect(1325, 140, 426, 291))
        self.orders_list.setWordWrap(True)
        self.orders_label = QtWidgets.QLabel(self.central_widget)
        self.orders_label.setGeometry(QtCore.QRect(1330, 115, 91, 16))
        self.orders_label.setText("Orders:")
        self.orders_label.setFont(font)

        self.bottled_list = QtWidgets.QListWidget(self.central_widget)
        self.bottled_list.setGeometry(QtCore.QRect(1325, 465, 431, 296))
        self.bottled_list.setWordWrap(True)
        self.bottled_label = QtWidgets.QLabel(self.central_widget)
        self.bottled_label.setGeometry(QtCore.QRect(1330, 440, 200, 16))
        self.bottled_label.setText("Bottled and ready:")
        self.bottled_label.setFont(font)

        self.file_dir_edit = QtWidgets.QLineEdit(self.central_widget)
        self.file_dir_edit.setGeometry(QtCore.QRect(467, 10, 341, 22))
        self.file_dir_edit.setText("Enter file directory for new csv file")
        self.add_file_button = QtWidgets.QPushButton(self.central_widget)
        self.add_file_button.setGeometry(QtCore.QRect(810, 7, 81, 26))
        self.add_file_button.setText("Add File")
        self.add_file_button.clicked.connect(self.add_file)

        self.explain_label = QtWidgets.QLabel(self.central_widget)
        self.explain_label.setGeometry(QtCore.QRect(900, 765, 846, 71))
        self.explain_label.setText("Prediction - Calculated by multiplying "
                                   "latest sales data with daily growth rates.\n\n"
                                   "Suggestions - Obtained by looking 6 weeks "
                                   "into the future and calculating beer "
                                   "with the most demand, along with the available equipment")

        main_window.setCentralWidget(self.central_widget)
        QtCore.QMetaObject.connectSlotsByName(main_window)

        LOGGER.info("Finished creating user interface")
        # Refresh the page.
        self.refresh_page()

        # Constantly save the batches and tanks.
        process = Thread(target=save_continuously, args=(), daemon=True)
        process.start()
        LOGGER.debug("New thread started")


if __name__ == "__main__":
    LOGGER.info("Starting Program")
    if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
        LOGGER.info("High Dpi scaling enabled")
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
        LOGGER.info("High Dpi Pixmaps enabled")
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    APP = QtWidgets.QApplication(sys.argv)
    WINDOW = QtWidgets.QMainWindow()
    UI = UiMainWindow(WINDOW)
    WINDOW.show()
    sys.exit(APP.exec_())
