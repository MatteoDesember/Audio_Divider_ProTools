import os
import re
from itertools import islice
import tkinter as tk
from tkinter import filedialog
from collections import Counter
from pydub import AudioSegment
import pandas as pd


def divide_audio(audio, group_table_num):
    """
    divide_audio splits one audio file into many parts.
    group_table_num contains split time array [start_time, end_time] and file_name
    """
    # Create output folder if no exists
    if not os.path.exists(TEMP_FOLDER):
        os.makedirs(TEMP_FOLDER)
    for index, [[start_time, end_time], file_name], in enumerate(group_table_num):
        # Convert time given in string into milliseconds
        start_time_milliseconds = text_to_milliseconds(start_time)
        end_time_milliseconds = text_to_milliseconds(end_time)

        # Create path for splitted audio
        part_audio_path = TEMP_FOLDER + "\\{}.wav".format(file_name)

        # Split audio
        part_audio = audio[start_time_milliseconds:end_time_milliseconds]

        # Export audio
        part_audio.export(part_audio_path, format="wav")
        print("Dividing " + str(index + 1) + "/" + str(len(group_table_num)) + " OK!")


def text_to_milliseconds(text):
    """text_to_milliseconds function convert given text in "m:s.fff" format into milliseconds, so it is easy to compare"""
    # Split text into minutes, seconds and milliseconds
    minutes, seconds, milliseconds = re.split("[:.]", text)
    return int(minutes) * 60 * 1000 + int(seconds) * 1000 + int(milliseconds)


def check_global_table(main_table_num, group_table_num):
    """
    check_global_table compares main_table_num to group_table_num
    if start time and end time for every group is found in clip table is ok
    Otherwise user should change groups in ProTools session
    """
    iterator = 0  # iterator point on analyzing element in group_table
    ok = True
    # For each group in group track
    for index, [start_time_group, end_time_group] in enumerate(group_table_num):
        start_ok = False
        end_ok = False
        # row_pointer points on main_table row
        row_pointer = 0
        # Find start time and end time in main track
        # Start iterating from iterator
        for start_time_main, end_time_main in islice(main_table_num, iterator, None):
            if text_to_milliseconds(start_time_group) == text_to_milliseconds(start_time_main):
                # Found start
                start_ok = True
            if text_to_milliseconds(end_time_group) == text_to_milliseconds(end_time_main):
                # Found end
                end_ok = True
                # Break loop here because next iterations are unused.
                break
            if text_to_milliseconds(start_time_group) < text_to_milliseconds(start_time_main) and text_to_milliseconds(
                    end_time_group) < text_to_milliseconds(end_time_main):
                # Break loop here because next iterations are unused
                break
            row_pointer += 1

        # if found start and end in main_table
        if start_ok and end_ok:
            print("Checking... " + str(index + 1) + "/" + str(group_table_num.shape[0]) + " OK!")
            # move iterator to point where found last start, end time
            iterator += row_pointer
        # Else group in Pro Tools session should be changed
        else:
            print(str(index + 1) + "/" + str(group_table_num.shape[0]) + " Start " + str(start_ok) + " End " + str(
                end_ok) +
                  " <---ERROR ")
            ok = False
    return ok


def process_pro_tools_file(lines):
    """
    process_pro_tools_file processes ProTools.txt file
    This function finds two tables (main_table, group_table)
    and return their start, end indexes
    """
    table_list = []  # list contains two dictionary: indexes when table start and their name
    dictionary = {}  # dictionary contains table start index and name
    for index, line in enumerate(lines):
        if 'TRACK NAME' in line:
            dictionary["TRACK_NAME_INDEX"] = index
        elif 'CHANNEL' in line:
            dictionary["CHANNEL_INDEX"] = index
            table_list.append(dictionary)
            dictionary = {}
    return table_list


def open_file_dialog():
    """open_file_dialog opens file dialog and return selected file chosen by user as string"""
    root = tk.Tk()
    root.withdraw()
    file = tk.filedialog.askopenfilename()
    # file_dir = os.path.dirname(os.path.abspath(file))
    # file_name = os.path.basename(os.path.abspath(file))
    return file


def select_file(default_file_dir):
    """
    select_file function opens file given in default_file_dir or after selecting file with open file dialog
    if it can't open file return False
    """
    file_dir = default_file_dir
    try:
        # Try to open default file
        if os.path.isfile(file_dir):
            file = open(file_dir)
        else:
            # Try to open file from file dialog
            print("Select file " + default_file_dir)
            file_dir = open_file_dialog()
            file = open(file_dir)
        print("Open file " + file_dir)
        return file, file_dir
    except Exception:
        print("Cant open default file " + default_file_dir + ", or did not select file <--- ERROR")
        return False, False


def process_protools_file(default_file_dir):
    """
    process_protools_file function checks if start_time and end_time
    in group_table and main_table (group_track and main_track) matched
    if so return True and group_track wchich is numpy array with start and end time
    """
    pro_tools_file, pro_tools_file_dir = select_file(default_file_dir=default_file_dir)

    if pro_tools_file:
        print("Read file: " + pro_tools_file_dir + " OK!")
        lines = pro_tools_file.readlines()

        # Find main_table and group_table indexes
        pro_tools_table_list = process_pro_tools_file(lines)

        # Read ProTools file by Padnas
        # main_table contains all clips
        # group_table contains all group
        main_table = pd.read_csv(pro_tools_file_dir, sep="\t", skiprows=pro_tools_table_list[0]["CHANNEL_INDEX"],
                                 nrows=(pro_tools_table_list[1]["TRACK_NAME_INDEX"] - pro_tools_table_list[0][
                                     "CHANNEL_INDEX"] - 3), skipinitialspace=True, encoding=pro_tools_file.encoding)
        group_table = pd.read_csv(pro_tools_file_dir, sep="\t", skiprows=pro_tools_table_list[1]["CHANNEL_INDEX"],
                                  skipinitialspace=True, encoding=pro_tools_file.encoding)

        # Remove blank spaces in each columns
        main_table.columns = main_table.columns.str.strip()
        group_table.columns = group_table.columns.str.strip()

        # Convert START TIME, END TIME columns into numpy arrays
        main_table = main_table[['START TIME', 'END TIME']].to_numpy()
        group_table = group_table[['START TIME', 'END TIME']].to_numpy()

        # Check if regions given in group_table starts and ends exactly where main audio starts and ends
        is_ok = check_global_table(main_table, group_table)
        print("--- ", is_ok, " ---")
        return is_ok, group_table


def process_filenames_file(default_file_dir, how_many_files):
    """
    process_filenames_file processes filenames file. This function checks if there is no duplicates
    and if there is as filenames as group start_times, end_times
    """
    new_file_names, new_file_names_dir = select_file(default_file_dir=default_file_dir)
    if new_file_names:

        # Remove end lines (\r\n) from new_names, and remove unallowed characters
        file_names = []
        for file_name in new_file_names.read().splitlines():
            f_n = re.sub("[\\\\/:*?\"<>|]", "", file_name)

            file_names.append(f_n)

        # Check if new_file_names contains sufficient amount of new names
        # New names can't contains duplicates
        if len(file_names) == how_many_files and len(set(file_names)) == how_many_files:
            return file_names

        else:
            # Print founded duplicates
            print(str(len(file_names)) + "!=" + str(how_many_files))
            print("Duplicates: ", [k for k, v in Counter(file_names).items() if v > 1])

            # If there is a file with new names and there are incompatibilities stop splitting audio
            return False
    else:
        print("There is no newFileNames <--- WARNING")
        # If there is no new file names, assign numbers as file names (1.wav, 2.wav, etc.)
        return range(1, how_many_files + 1)


def process_wav_file(default_file_dir, wav_file_names):
    """process_wav_file processes wav file and split it into parts"""
    # Choose audio to split
    wav_file, wav_file_dir = select_file(default_file_dir=default_file_dir)
    if wav_file:
        # Divide audio
        divide_audio(AudioSegment.from_wav(wav_file_dir), wav_file_names)


# This is output folder
TEMP_FOLDER = 'ProTools'

while True:
    """This is little console for user"""
    to_do = input("Tell me what do you wanna do: \r\n")
    if to_do == 'exit' or to_do == 'e':
        break
    elif to_do == 'pt':  # divide audio into parts
        protools_file_ok, group_table = process_protools_file(default_file_dir='ProTools.txt')
        if protools_file_ok:
            file_names = process_filenames_file(default_file_dir='newFileNames.txt',
                                                how_many_files=len(group_table))

            # If everything with ProTools.txt and file names looks good
            if file_names:
                group_table_with_file_names = list(zip(group_table, file_names))
                process_wav_file(default_file_dir='ProTools.wav', wav_file_names=group_table_with_file_names)
            else:
                print("There is problem with fileNames file")

    else:
        print("There is no such a command")
