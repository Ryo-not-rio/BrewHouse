"""
This module deals with the prediction of sales for a year into the future.

This is done by finding the growth rates for each day in the csv file and multiplying
that to the latest data point for each beer over and over until all the growth rates have
been multiplied.
In addition, the module can plot past data and the prediction using
matplotlib and find the total predicted sale of a given time period.
"""
import os
from datetime import datetime, timedelta
from typing import List, Tuple, Dict
import logging
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from read_file import parse_data


ABS_PATH = os.path.abspath(__file__)
D_NAME = os.path.dirname(ABS_PATH)
os.chdir(D_NAME)

LOGGER = logging.getLogger("sales_predictions")
LOGGER.setLevel(logging.DEBUG)
F_HANDLER = logging.FileHandler('log_file.log')
F_FORMAT = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
F_HANDLER.setFormatter(F_FORMAT)
LOGGER.addHandler(F_HANDLER)


def calculate_growth(start_date_obj: datetime, end_date_obj: datetime,
                     x_list: List[datetime], y_list: List[int], days: int = 1) -> int:
    """
    This function calculates the growth % given two dates and the sales for those dates.

    This function can also calculate the growth rate between two periods.

    :param start_date_obj: First date.
    :param end_date_obj: Second date.
    :param x_list: List of dates.
    :param y_list: List of sales.
    :param days: Length of time period.

    :return: Growth % as a rounded integer.
    """
    x_index = x_list.index(start_date_obj)
    start_data = sum(y_list[x_index:x_index+days])  # Summing the sales values for the given period.
    if start_data == 0:
        # Setting a default replacement value for 0 so prediction division by 0 doesn't occur.
        LOGGER.debug("Start data changed to 1.1")
        start_data = 1.1
    x_index = x_list.index(end_date_obj)
    if x_index+days <= len(y_list):
        # Summing the sales values in the next given period.
        end_data = sum(y_list[x_index:x_index+days])
    else:
        end_data = sum(y_list[x_index:])  # If the end of the list is reached.
    growth_percent = round((end_data - start_data) / start_data, 5) * 100
    return growth_percent


def multiply_rate(value: int, percent_list: List[int],
                  index: int = 0, new_list: List = None) -> List[int]:
    """
    This function multiplies all the growth rates recursively.

    :param value: Value for the growth % to be applied to.
    :param percent_list: List of growth %.
    :param index: Index of the growth % to be applied.
    :param new_list: List of the new values after growth % was applied.

    :return: After recursion is finished, a list of the new values is returned.
    """
    if new_list is None:
        new_list = []

    if index >= len(percent_list):
        return new_list
    value += 1  # To avoid the prediction flat-lining.
    value *= ((percent_list[index]) / 100) + 1
    new_list.append(value)
    index += 1
    return multiply_rate(value, percent_list, index, new_list)


def plot_past_data(key_name: str = None) -> List[Line2D]:
    """
    This function plots the past data using matplotlib.

    The optional argument allows you to see the graph for only one beer type.

    :param key_name: A specific type of beer to be shown.
    :return: The plot.
    """
    LOGGER.info("Plotting past data")
    data_dict = parse_data()
    for key in data_dict['x']:
        if key_name is None or key == key_name:
            x_data = data_dict['x'][key]
            y_data = data_dict['y'][key]
            line_2d = plt.plot(x_data, y_data, label=key, marker=".", linewidth=0.5, markersize=1)

    plt.legend()
    return line_2d


def plot_growth_percent(days: int = 1, key_name: str = None, plot: bool = True,
                        start_date: datetime = None) -> Tuple[List[datetime], Dict[str, List[int]]]:
    """
    This function returns the growth rates for each beer.

    The growth can be calculated for a total of a given period or day by day. It can
    also be calculated for all the beers or just one specific beer.
    This module also has the capability to plot the grow rates using matplotlib.

    :param days: The period to sum the data.
    :param key_name: The name of the specific beer.
    :param plot: Whether to plot the graph or not.
    :param start_date: The date to start the growth rate list from.

    :return: A dictionary of the growth rates and the corresponding dates.
    """
    LOGGER.info("Calculating growth rates")
    data_dict = parse_data()
    growth_dict = {}

    for key in data_dict['x']:  # Iterating through each beer.
        if key_name is None or key_name == key:
            x_data, y_data = data_dict['x'][key], data_dict['y'][key]

            growth_rates = []
            dates = []

            # Iterating through the dates in required steps.
            for index in range(0, len(x_data)-days, days):
                date = x_data[index]
                if start_date is None or start_date <= date:
                    dates.append(date)
                    growth = calculate_growth(date, date + timedelta(days), x_data, y_data, days)
                    growth_rates.append(growth)
            LOGGER.debug("Data and date added")

            growth_dict[key] = growth_rates

            if plot:
                plt.plot(dates, growth_rates,
                         label=key + " growth % "+str(days),
                         linestyle='None', marker="D", markersize=2)

    if plot:
        plt.legend()
    return dates, growth_dict


def plot_next_year(days: int = 1, key_name: str = None, next_year: bool = True,
                   start_date: datetime = None, date_range: int = None)\
        -> Tuple[List[datetime], Dict[str, List[int]]]:
    """
    This module calculates the predictions for 1 year from the latest data in the csv file.

    The module has several options including calculating the data for just the given period.
    A prediction is made by calculating the growth rates per day in the csv file, and multiplying
    that to the latest sales made in the csv file.

    :param days:
    The period in which to calculate growth.
    Set this to values other than one to predict using time periods.
    :param key_name: Can be set to find the prediction for just one beer.
    :param next_year: Whether to adjust the dates for prediction.
    :param start_date: The date to start the prediction from.
    :param date_range: The number of days in the future the prediction should go on for.

    :return: A dictionary of predicted data and the corresponding dates.
    """
    LOGGER.info("Calculating next year")
    data_dict = parse_data()
    start_past_date = data_dict['x']['Organic Red Helles'][-1] - timedelta(days=364)
    dates, percent_dict = plot_growth_percent(days=days, key_name=key_name, plot=False,
                                              start_date=start_past_date)

    if dates is None:
        return None, None

    dates = [date + timedelta(days=days-1) for date in dates]
    prediction_dict = {}

    if next_year:
        dates = [date + timedelta(days=365) for date in dates]

    # Start date + date range is larger than date list
    if start_date is not None and start_date + timedelta(date_range) not in dates:
        return False, False

    for key, percent_list in percent_dict.items():
        start_sale = data_dict['y'][key][-1]

        LOGGER.debug("Multiplying rate")
        prediction_dict[key] = multiply_rate(start_sale, percent_list)

        if start_date is not None:
            index = dates.index(start_date)
            prediction_dict[key] = prediction_dict[key][index:]
        if date_range is not None:
            prediction_dict[key] = prediction_dict[key][:date_range]

    LOGGER.debug("All rates multiplied")
    if start_date is not None:
        dates = dates[index:]
    if date_range is not None:
        dates = dates[:date_range]

    return dates, prediction_dict


def get_total(start_date: datetime, date_range: datetime,
              data_tuple: Tuple[List[datetime], Dict[str, List[int]]]) -> Dict[str, int]:
    """
    This module gets the total sales in a given time period.

    :param start_date: The date to start counting the sales.
    :param date_range: The period in which to calculate the total.
    :param data_tuple: The list of dates and the dictionary which holds the sales data.

    :return:
    A dictionary containing the total for each beer.
    """
    LOGGER.info("Getting total from %s", str(start_date))
    dates, data = data_tuple
    return_dict = {}
    for key, batch in data.items():
        if start_date not in dates:
            LOGGER.warning("start date not in dates")
            return None

        index = dates.index(start_date)
        if index + date_range >= len(batch):
            LOGGER.warning("Date range out of range of batch list")
            return None

        return_dict[key] = sum(batch[index:index+date_range])
    return return_dict


if __name__ == "__main__":
    plot_past_data(key_name="Organic Pilsner")
    # plot_next_year(days=1, key_name="Organic Pilsner", next_year=False)
    # plot_growth_percent(days=7, key_name="Organic Pilsner")
    # plot_average_growths(days=3, key_name="Organic Pilsner")
    # dates, data = plot_next_year(plot=False)
    # print(get_total(datetime(2019, 12, 2), 7, dates, data))
    plt.show()
