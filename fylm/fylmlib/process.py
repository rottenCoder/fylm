# -*- coding: utf-8 -*-
# Copyright 2018 Brandon Shelley. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Main application logic.

This module scans for and processes films.

    process: the main class exported by this module.
"""

from __future__ import unicode_literals, print_function

import os

from fylmlib.config import config
from fylmlib.console import console
import fylmlib.operations as ops
import fylmlib.counter as counter

class process:
    """Main class for scanning for and processing films.

    All methods are class methods, thus this class should never be instantiated.
    """

    # TODO: (Possible) handle multiple editions stored in the same folder.
    @classmethod
    def file(cls, film):
        """Process a single file film object.

        Args:
            film: (Film) film object to process.
        """

        # Rename the source file to its new filename
        ops.fileops.rename(film.source_path, film.new_filename__ext(), film.size)

        # Update the source path of the film if we're running in live mode
        # to its new name, otherwise the move will fail (because it will 
        # be looking for its original filename).
        if config.test is False:
            film.source_path = os.path.normpath(os.path.join(os.path.dirname(film.source_path), film.new_filename__ext()))

        # Generate a new source path based on the new filename and the
        # destination dir.
        dst = os.path.normpath(os.path.join(film.destination_dir, film.new_filename__ext()))

        console.info('Moving to {}'.format(dst))

        # Move the file. (Only executes in live mode).
        if ops.fileops.safe_move(film.source_path, dst):

            # If move was successful, update the counter.
            counter.add(1)

        # Update the film's source_path again with its final destination.
        film.source_path = dst

    @classmethod
    def dir(cls, film):
        """Process a directory film object.

        Args:
            film: (Film) film object to process.
        """

        # Create a local counter to track deleted (unwanted) files.
        deleted_files_count = 0

        # Create a list for files to queue. This is used to guarantee
        # uniqueness in name.
        queued_files = []

        # Enumerate valid files.
        for file in film.valid_files:

            # Generate new filename based on film's corrected name and
            # the iterated file's extension.
            new_filename__ext = film.new_filename__ext(os.path.splitext(file)[1])

            # Generate new source and destination paths based on the new filename
            src = os.path.normpath(os.path.join(os.path.dirname(file), new_filename__ext))
            dst = os.path.normpath(os.path.join(film.destination_dir, new_filename__ext))

            # Append the destination to the queued files list
            queued_files.append(dst)

            # Check if a file with the same name exists more than once in the queue.
            # If so, handle the filename conflict by appending a number to the filename.
            # e.g. My Little Pony.srt would become My Little Pony.1.srt if its already
            # in the queue.
            if queued_files.count(dst) > 1:
                filename, ext = os.path.splitext(dst)
                dst = '{}.{}{}'.format(filename, queued_files.count(dst) - 1, ext)
                src = os.path.normpath(os.path.join(os.path.dirname(file), os.path.basename(dst)))

            # Rename the source file to its new filename
            ops.fileops.rename(file, os.path.basename(dst), ops.size(file))

            console.info('Moving to {}'.format(dst))

            # Move the file. (Only executes in live mode).
            if ops.fileops.safe_move(src, dst):

                # If move was successful, update the counter.
                counter.add(1)

        # Recursively delete unwanted files and update the count.
        deleted_files_count = ops.dirops.delete_unwanted_files(film.source_path, deleted_files_count)

        # Update the film's source_path to the new location of its parent folder at 
        # the destination once all files have been moved.
        film.source_path = film.destination_dir

        # Print results of removing unwanted files.
        if config.remove_unwanted_files and deleted_files_count > 0:
            console.notice('Cleaned {} unwanted file{}'.format(deleted_files_count, '' if deleted_files_count == 1 else 's'))

        # Remove the original source parent folder, if it is safe to do so (and
        # the feature is enabled in config). First check that the source folder is
        # empty, and that it is < 1 KB in size. If true, remove it. We also
        # don't want to try and remove the source folder if the original source
        # is the same as the destination.
        if config.remove_source and film.original_path != film.destination_dir:
            console.debug('Removing parent folder {}'.format(film.original_path))

            # Max size a dir can be to qualify for removal
            max_size = 1000
            if (ops.size(film.original_path) < max_size and ops.dirops.count_files_deep(film.original_path) == 0) or config.test:

                # Check that the file is smaller than max_size, and deep count the number
                # of files inside. Automatically ignores system files like .DS_Store.
                # If running in test mode, we 'mock' this response by pretending the folder
                # was removed.
                console.notice('Removing parent folder')
                ops.dirops.delete_dir_and_contents(film.original_path, max_size)
            else:

                # If the parent folder fails the deletion qualification, print to console.
                console.warn('Will not remove parent folder because it is not empty')