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

"""Duplicate handling for films.

This module handles all the duplicate checking and handling logic for Fylm.
"""
from __future__ import unicode_literals, print_function

from itertools import ifilter

from fylmlib.config import config
from fylmlib.console import console
import fylmlib.compare as compare
import fylmlib.operations as ops
import fylmlib.formatter as formatter
import fylmlib.existing_films as existing_films

def check(film):
    """Get a list of duplicates from a list of existing films.

    Compare the film objects to an array of exsiting films in
    order to determine if any duplicates exist at the destination.
    Criteria for a duplicate: title, year, and edition must match (case insensitive).

    Returns:
        A an array of duplicate films.
    Args:
        film (Film): Film object to check for duplicates.
    """

    # If check for duplicates is disabled, return an empty array (because we don't care if they exist).
    # DANGER ZONE: With check_for_duplicates disabled and overwrite_existing enabled, any files
    # with the same name at the destination will be silently overwritten.
    if config.duplicate_checking.enabled is False or config.rename_only is True:
        console.debug('Duplicate checking is disabled, skipping.')
        return []

    console.debug('Searching for duplicates of "{}" ({})'.format(film.title, film.year))

    # Filter the existing_films cache array to titles beginning with the first letter of the
    # current film, then use fast ifilter to check for duplicates. Then we filter out empty folder,
    # folders with no valid media folders, and keep only non-empty folders and files.
    # TODO: Add tests to ensure this works for 'title-the' naming convention as well.
    duplicates = list(ifilter(lambda d:
            # First letter of the the potential duplicate's title must be the same.
            # Checking this first allows us to have a much smaller list to compare against.
            d.title[0] == film.title[0]

            # Check that the film is actually a duplicate in name/year/edition
            and compare.is_duplicate(film, d)

            and ((
                d.is_dir
                # If the potential duplicate is a dir, check that it contains at least
                # one valid file.
                and len(ops.dirops.get_valid_files(d.source_path)) > 0)

                # Or if it is a file, it is definitely a duplicate.
                or d.is_file),

        # Perform the filter against the existing films cache.
        existing_films.cache))

    console.debug('   Total duplicate(s) found: {}'.format(len(duplicates)))
    return duplicates

def should_replace(film, duplicate):
    """Determines if a duplicate should be replaced.

    Config settings govern whether a duplicate can be replaced if it is of
    a specific quality, e.g. a 1080p can be allowed replace a 720p, but a
    2160p cannot.
    
    Args:
        film (Film): Film object to determine if it should replace a duplicate.
        duplicate (Film or path): Verified duplicate object to check `film` against.
    Returns:
        True if `film` should replace `duplicate`.
    """

    # If duplicate replacing is disabled, don't replace.
    if config.duplicate_replacing.enabled is False:
        return False

    # If the duplicate is a path and not a film, we need to load it.
    from fylmlib.film import Film
    if not isinstance(duplicate, Film):
        duplicate = Film(duplicate)

    # Replace quality takes a dict of arrays for each quality, which governs whether
    # a specific quality has the ability to replace another. By default, this map
    # looks like:
    #   2160p: [] # Do not replace 2160p films with any other quality
    #   1080p: [] # Do not replace 1080p films with any other quality
    #   720p: ['1080p'] # Replace 720p films with 1080p
    #   SD: ['1080p', '720p'] # Replace standard definition (or unknown quality) 
    #       with 1080p or 720p
    if film.quality in config.duplicate_replacing.replace_quality[duplicate.quality or 'SD']:
        return True

    # Or, if quality is the same and the size is larger, 
    elif (config.duplicate_replacing.replace_smaller is True
        and film.quality == duplicate.quality 
        and film.size > duplicate.size):
        return True

    # Otherwise it should not be replaced.
    else:
        return False

def should_keep_both(film, duplicate):
    """Determines if both a film and a duplicate should be kept.

    Under certain conditions, both a film and a duplicte should be kept.
    
    Args:
        film (Film): Film object to determine if it should replace a duplicate.
        duplicate (Film or path): Duplicate object to check `film` against.
    Returns:
        True if `film` and `duplicate` should both be kept, else False.
    """

    # If the duplicate is a path and not a film, we need to load it.
    from fylmlib.film import Film
    if not isinstance(duplicate, Film):
        duplicate = Film(duplicate)

    # If new and existing films have a different quality, and the new film is larger 
    # (better), if the new film doesn't qualify as a replacement, we can assume that 
    # we want to keep both the current film and the duplicate.
    return (film.quality != duplicate.quality 
        and not should_replace(film, duplicate)
        and film.size > duplicate.size)