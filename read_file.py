"""This module deals with reading the csv file and adding to it"""
import os
import csv
from datetime import timedelta, datetime
from typing import Dict, List, Union
import logging
from pandas import read_csv, concat
from pandas.errors import ParserError
from dateutil.parser import parse

ABS_PATH = os.path.abspath(__file__)
D_NAME = os.path.dirname(ABS_PATH)
os.chdir(D_NAME)

LOGGER = logging.getLogger("inv_management")
LOGGER.setLevel(logging.DEBUG)
F_HANDLER = logging.FileHandler('log_file.log')
F_FORMAT = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
F_HANDLER.setFormatter(F_FORMAT)
LOGGER.addHandler(F_HANDLER)


def parse_data() -> Dict[str, Dict[str, List[Union[datetime, int]]]]:
    """
    Parses the data in the csv to a dictionary in the following structure.

    {'x': {'Beer1': [date1, date2, date3...],
       'Beer2': [date1, date2, date3...],
       'Beer3': [date1, date2, date3...]}
    'y': {'Beer1': [value1, value2, value3...],
       'Beer2': [value1, value2, value3...],
       'Beer3': [value1, value2, value3...]}}

    :return: Parsed data.
    """
    LOGGER.info("Reading the csv file")
    try:
        with open('Barnabys_sales_fabriacted_data.csv') as file:
            # Adding missing data to the beginning
            data_dict = {'x': {'Organic Red Helles': [datetime(2018, 11, 1)],
                               'Organic Dunkel': [datetime(2018, 11, 1)]},
                         'y': {'Organic Red Helles': [0], 'Organic Dunkel': [0]}}

            # Iterating through each row, ignoring the header.
            for row in list(csv.reader(file, delimiter=','))[1:]:
                # row[3] is the beer name
                # If the beer has not been added to the dictionary yet
                if row[3] not in data_dict['x'].keys():
                    data_dict['x'][row[3]] = []
                    data_dict['y'][row[3]] = []

                date_obj = parse(row[2])
                quantity = int(row[5])
                # If date to be added exists, add sales to the existing data.
                # If it doesn't, add the date and sale to the dictionary.
                if date_obj not in data_dict['x'][row[3]]:
                    data_dict['x'][row[3]].append(date_obj)
                    data_dict['y'][row[3]].append(quantity)
                else:
                    # Adding sale to existing sale value
                    data_dict['y'][row[3]][data_dict['x'][row[3]].index(date_obj)] += quantity
            LOGGER.debug("Initial reading done")

            # Sorting each list in the dictionaries.
            for key, x_beer in data_dict['x'].items():
                data_dict['y'][key] = [x for _, x in sorted(zip(x_beer, data_dict['y'][key]))]
                data_dict['x'][key] = sorted(x_beer)

            # If the latest dates don't match, add dates so the latest date matches.
            last_date_list = [item[-1] for item in data_dict['x'].values()]
            if not (last_date_list[0] == last_date_list[1]
                    and last_date_list[1] == last_date_list[2]):
                for key, value in data_dict['x'].items():
                    if max(last_date_list) not in value:
                        data_dict['x'][key].append(max(last_date_list))
                        data_dict['y'][key].append(0)
                LOGGER.debug("Latest date matched")

            for key, x_beer in data_dict['x'].items():
                # Filling in the gaps with sales of 0.
                for counter, (date_obj, quantity) in \
                        enumerate(zip(x_beer[:-1], data_dict['y'][key][:-1])):
                    next_date_obj = x_beer[counter+1]
                    gap = (next_date_obj - date_obj).days - 1

                    for i in range(gap):
                        get_date_obj = date_obj + timedelta(days=1+i)
                        new_quantity = 0
                        x_beer.append(get_date_obj)
                        data_dict['y'][key].append(new_quantity)

                # Sorting the data in case it got mixed while filling in gaps.
                data_dict['y'][key] = [x for _, x in sorted(zip(x_beer, data_dict['y'][key]))]
                data_dict['x'][key] = sorted(x_beer)
                LOGGER.debug("Filled gap and sorted %s", key)
    except FileNotFoundError:
        LOGGER.critical("CSV File Not Found")

    return data_dict


def write_data(file_dir: str) -> str:
    """
    This function adds data from a csv file in the given the directory.

    :param file_dir: The directory of the csv file to be added.
    :return: Error message.
    """
    LOGGER.info("Writing csv data#")
    try:
        open(file_dir)
    except FileNotFoundError:
        return "File not found"

    try:
        file_a = read_csv('Barnabys_sales_fabriacted_data.csv', index_col=0)
        file_b = read_csv(file_dir, index_col=0)
        concat([file_a, file_b]).to_csv('Barnabys_sales_fabriacted_data.csv')
        return "success"
    except FileNotFoundError:
        LOGGER.error("csv file was not found")
        return "file not found"
    except ParserError:
        LOGGER.error("Invalid data in new csv file")
        return "Valid data not found in file"


DATA_DICT = parse_data()

if __name__ == "__main__":
    print(parse_data())
