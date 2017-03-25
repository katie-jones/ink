#!/usr/bin/python3

import unittest
import tempfile
import os
import stat
import ink
import glob
import time
import copy
import configparser

class RunBackupsUnitTest(unittest.TestCase):
    ''' Unit test for ink.py. '''
    def setUp(self):
        '''
        Set up the tests by:
            - Creating a temporary directory where the test backups and files should be held.
            - Creating a configuration file for the backups.
            - Initializing the files that will be backed up.
        '''
        # Create a temporary directory where test backups and files will be
        # held.
        self.root_dir = tempfile.TemporaryDirectory()

        # Create subdirectories to hold the original files and their backups.
        self.orig_dirname = os.path.join(self.root_dir.name, 'orig')
        self.backups_container_dirname = os.path.join(self.root_dir.name, 'backup')
        os.makedirs(self.orig_dirname)
        os.makedirs(self.backups_container_dirname)

        # Create logfile for backups
        self.log_filename = os.path.join(self.root_dir.name, 'ink.log')

        # Define prefix for backups
        self.backup_prefix = 'backups-'

        # Define symlink name for most recent backups
        self.link_name = 'current'

        # Create config file for backups
        self.config_filename = os.path.join(self.root_dir.name, 'test.cfg')

        # Set directory names for log and cache
        self.log_directory = os.path.join(self.root_dir.name, 'log')
        self.cache_directory = os.path.join(self.root_dir.name, 'cache')

        # Create some files and directories to back up
        # Structure is:
        # +-- a (This is file a.)
        # +-- dir/
        # |   +-- b (This is file b in dir.)
        self.files = []
        self.files.append({'name': 'a', 'contents': 'This is file 1.'})
        self.files.append({'name': 'dir/b', 'contents': 'This is file 2.'})
        self._create_original_files(self.files)

        # Define command line arguments for running backups
        self.argv = [self.config_filename, '--ignore-system-config',
                     '--log-directory', self.log_directory,
                     '--cache-directory', self.cache_directory]

    def _write_config_file(self, config):
        ''' Write the configuration given in dict config to the config file.'''
        parser = configparser.ConfigParser()
        parser.read_dict(config)
        with open(self.config_filename, 'w') as configfile:
            parser.write(configfile)

    def _get_testing_config(self):
        '''
        Return the default testing configuration as a dict.
        '''
        config = dict()
        config['testing'] = {'mount_point': '',
                             'backup_folder': self.backups_container_dirname,
                             'to_backup': self.orig_dirname,
                             'backup_type': 'incremental',
                             'exclude_file': '',
                             'UUID': '',
                             'partition_label': '',
                             'partition_device': '',
                             'link_name': 'current',
                             'folder_prefix': 'backup-',
                             'frequency_seconds': '0',
                             'rebase_root': 'false'
                             };
        return config

    def _create_original_files(self, files):
        ''' Create the files given in directory self.orig_dirname.'''
        # Loop through files and create them
        for filecfg in files:
            # Make directory if it doesn't exist
            try:
                os.makedirs(os.path.join(self.orig_dirname,
                                         os.path.dirname(filecfg['name'])))
            except FileExistsError:
                pass

            # Check if the contents of the file are equal
            try:
                update_file = True
                with open(os.path.join(self.orig_dirname, filecfg['name']),
                          'r') as testfile:
                    update_file = (testfile.read() != filecfg['contents'])
            except FileNotFoundError:
                pass

            # Print new contents if they have changed
            if update_file:
                print('Updating file {:s} to read {:s}'.format(filecfg['name'],
                                                               filecfg['contents']))
                with open(os.path.join(self.orig_dirname, filecfg['name']), 'w') \
                        as testfile:
                    testfile.write(filecfg['contents'])

    def _compare_directory_content(self, files, dirname):
        ''' Run through the list of files and check that they exist in
        directory dirname and that their contents match.'''
        # Check that all files in original directory exist in backup directory
        # and have identical contents
        for filecfg in files:
            with open(os.path.join(dirname, filecfg['name']), 'r') \
                    as testfile:
                self.assertEqual(testfile.read(), filecfg['contents'])

    @staticmethod
    def _is_hard_link(filename1, filename2):
        ''' Returns true if the two filenames are hardlinks to the same
        file.'''
        s1 = os.stat(filename1)
        s2 = os.stat(filename2)
        return (s1[stat.ST_INO], s1[stat.ST_DEV]) == \
            (s2[stat.ST_INO], s2[stat.ST_DEV])

    def test_make_incremental_backup(self):
        ''' Test that a simple backup can be made.'''
        print('')
        print('Running test make_incremental_backup.')
        # Set backup type to incremental
        config = self._get_testing_config()
        config['testing']['backup_type'] = 'incremental'
        self._write_config_file(config)

        # Run backups with the relevant command line arguments
        ink.main(self.argv)

        # Get the directory containing the most recent backups
        backup_dirname = os.path.realpath(
            os.path.join(self.backups_container_dirname, self.link_name))

        # Check that all files in original directory exist in backup directory
        # and have identical contents
        self._compare_directory_content(self.files, backup_dirname)

    def test_make_snapshot_backup(self):
        ''' Test that a simple snapshot backup can be made.'''
        print('')
        print('Running test make_snapshot_backup.')
        # Set backup type to snapshot
        config = self._get_testing_config()
        config['testing']['backup_type'] = 'snapshot'
        self._write_config_file(config)

        # Run backups with the relevant command line arguments
        ink.main(self.argv)

        # Get the directory containing the most recent backups
        backup_dirname = self.backups_container_dirname

        # Check that all files in original directory exist in backup directory
        # and have identical contents
        for filecfg in self.files:
            with open(os.path.join(backup_dirname, filecfg['name']), 'r') \
                    as testfile:
                self.assertEqual(testfile.read(), filecfg['contents'])

    def test_incremental_update_backup(self):
        ''' Test that an incremental backup updates itself. '''
        print('')
        print('Running test incremental_update_backup.')
        # Set backup type to incremental
        config = self._get_testing_config()
        config['testing']['backup_type'] = 'incremental'
        self._write_config_file(config)

        # Make backups of original files
        ink.main(self.argv)

        # Get the directory containing the first backups
        first_backup_dirname = os.path.realpath(
            os.path.join(self.backups_container_dirname, self.link_name))

        # Update one file
        updated_files = copy.deepcopy(self.files)
        updated_files[0]['contents'] += ' Updated.'
        self._create_original_files(updated_files)

        # Sleep for one second to make sure new backups will be run
        time.sleep(1)

        # Run backups again
        ink.main(self.argv)

        # Get the directory containing the most recent backups
        backup_dirname = os.path.realpath(
            os.path.join(self.backups_container_dirname, self.link_name))

        # Loop through newest backup folder and expect the content to be
        # updated.
        self._compare_directory_content(updated_files, backup_dirname)

        # For all files except the first (which was updated), expect the entry
        # in both backups to be a hardlink to the same file
        self.assertFalse(self._is_hard_link(
                os.path.join(first_backup_dirname, updated_files[0]['name']),
                os.path.join(backup_dirname, updated_files[0]['name'])))
        for filecfg in updated_files[1:]:
            self.assertTrue(self._is_hard_link(
                os.path.join(first_backup_dirname, filecfg['name']),
                os.path.join(backup_dirname, filecfg['name'])))

    def test_nolinks_update_backup(self):
        ''' Test that an incremental backup updates itself. '''
        print('')
        print('Running test nolinks_update_backup.')
        # Set backup type to nolinks
        config = self._get_testing_config()
        config['testing']['backup_type'] = 'nolinks'
        self._write_config_file(config)

        # Make backups of original files
        ink.main(self.argv)

        # Get the directory containing the first backups
        first_backup_dirname = os.path.realpath(
            os.path.join(self.backups_container_dirname, self.link_name))

        # Update one file
        updated_files = copy.deepcopy(self.files)
        updated_files[0]['contents'] += ' Updated.'
        self._create_original_files(updated_files)

        # Sleep for one second to make sure new backups will be run
        time.sleep(1)

        # Run backups again
        ink.main(self.argv)

        # Get the directory containing the most recent backups
        backup_dirname = os.path.realpath(
            os.path.join(self.backups_container_dirname, self.link_name))

        # The first directory now has a suffix of _bak
        first_backup_dirname += '_bak'

        # Loop through newest backup folder and expect the content to be
        # updated.
        self._compare_directory_content(updated_files, backup_dirname)

        # Expect the first backup directory to contain the first file
        self._compare_directory_content([self.files[0]],
                                        first_backup_dirname)

        # Expect all other files to not exist in first backup directory
        for filecfg in self.files[1:]:
            self.assertFalse(os.path.isfile(os.path.join(first_backup_dirname,
                                                         filecfg['name'])))

    def test_full_update_backup(self):
        ''' Test that a full backup updates itself. '''
        print('')
        print('Running test full_update_backup.')

        # Set backup type to full
        config = self._get_testing_config()
        config['testing']['backup_type'] = 'full'
        self._write_config_file(config)

        # Make backups of original files
        ink.main(self.argv)

        # Get the directory containing the first backups
        first_backup_dirname = os.path.realpath(
            os.path.join(self.backups_container_dirname, self.link_name))

        # Update one file
        updated_files = copy.deepcopy(self.files)
        updated_files[0]['contents'] += ' Updated.'
        self._create_original_files(updated_files)

        # Sleep for one second to make sure new backups will be run
        time.sleep(1)

        # Run backups again
        ink.main(self.argv)

        # Get the directory containing the most recent backups
        backup_dirname = os.path.realpath(
            os.path.join(self.backups_container_dirname, self.link_name))

        # Loop through newest backup folder and expect the content to be
        # updated.
        self._compare_directory_content(updated_files, backup_dirname)

        # Loop through the first backup folder and expect the content to be the
        # original
        self._compare_directory_content(self.files,
                                        first_backup_dirname)

        # Expect none of the files to be hardlinks
        for filecfg in updated_files[1:]:
            self.assertFalse(self._is_hard_link(
                os.path.join(first_backup_dirname, filecfg['name']),
                os.path.join(backup_dirname, filecfg['name'])))

    def test_snapshot_update_backup(self):
        ''' Test that a snapshot backup updates itself. '''
        print('')
        print('Running test snapshot_update_backup.')

        # Set backup type to snapshot
        config = self._get_testing_config()
        config['testing']['backup_type'] = 'snapshot'
        self._write_config_file(config)

        # Make backups of original files
        ink.main(self.argv)

        # Get the directory containing the most recent backups
        backup_dirname = self.backups_container_dirname

        # Get the modification times of the files
        modification_times = []
        for filecfg in self.files:
            modification_times.append(os.path.getmtime(os.path.join(backup_dirname,
                                                         filecfg['name'])))

        # Update one file
        updated_files = copy.deepcopy(self.files)
        updated_files[0]['contents'] += ' Updated.'
        self._create_original_files(updated_files)

        # Sleep for one second to make sure new backups will be run
        time.sleep(1)

        # Run backups again
        ink.main(self.argv)

        # Loop through newest backup folder and expect the content to be
        # updated.
        self._compare_directory_content(updated_files, backup_dirname)

        # Expect the first file to have a new, later modification time but the
        # others to be the same
        for index, filecfg in enumerate(updated_files):
            if index == 0:
                self.assertGreater(os.path.getmtime(os.path.join(backup_dirname,
                                                         filecfg['name'])),
                           modification_times[index])
            else:
                self.assertEqual(os.path.getmtime(os.path.join(backup_dirname,
                                                         filecfg['name'])),
                           modification_times[index])

    def test_rebase_root(self):
        ''' Test that the rebase_root option works.'''
        print('')
        print('Running test rebase_root.')
        # Set backup type to incremental
        config = self._get_testing_config()
        config['testing']['backup_type'] = 'incremental'

        # Set rebase_root option
        config['testing']['rebase_root'] = 'true'
        self._write_config_file(config)

        # Run backups with the relevant command line arguments
        ink.main(self.argv)

        # Get the directory containing the most recent backups
        backup_dirname = os.path.realpath(
            os.path.join(self.backups_container_dirname, self.link_name,
                         self.orig_dirname[1:]))

        # Check that all files in original directory exist in backup directory
        # and have identical contents
        self._compare_directory_content(self.files, backup_dirname)

    def test_frequency(self):
        ''' Test that the frequency option works.'''
        print('')
        print('Running test frequency.')
        # Set backup type to incremental
        config = self._get_testing_config()
        config['testing']['backup_type'] = 'incremental'

        # Set backup frequency
        frequency = 5
        config['testing']['frequency_seconds'] = '5' #'{:d}'.format(frequency)
        self._write_config_file(config)

        # Run backups with the relevant command line arguments
        first_backup_time = time.time()
        ink.main(self.argv)

        # Get the directory containing the most recent backups
        first_backup_dirname = os.path.realpath(
            os.path.join(self.backups_container_dirname, self.link_name))

        # Check that the time elapsed is less than the frequency and try making
        # backups again
        self.assertLess(time.time(), first_backup_time + frequency, msg =
                        'Frequency is too short. Increase the frequency and '
                        'run the test again.')
        ink.main(self.argv)

        # No new backup should be created
        backup_dirname = os.path.realpath(
            os.path.join(self.backups_container_dirname, self.link_name))
        self.assertEqual(backup_dirname, first_backup_dirname)

        # Wait until time elapsed is greater than frequency and try making
        # backups again
        time.sleep(frequency)
        self.assertGreater(time.time(), first_backup_time + frequency)
        ink.main(self.argv)

        # New backups should be created
        backup_dirname = os.path.realpath(
            os.path.join(self.backups_container_dirname, self.link_name))
        self.assertNotEqual(backup_dirname, first_backup_dirname)

    def test_default_exclude(self):
        '''
        Test that the folder containing the backups is excluded when it is a
        child of the directory being backed up.
        '''
        print('')
        print('Running test default_exclude.')
        # Set backup type to incremental
        config = self._get_testing_config()
        config['testing']['backup_type'] = 'incremental'

        # Backup the root directory
        config['testing']['to_backup'] = self.root_dir.name
        self._write_config_file(config)

        # Run backups with the relevant command line arguments
        ink.main(self.argv)

        # Get the directory containing the most recent backups
        backup_dirname = os.path.realpath(
            os.path.join(self.backups_container_dirname, self.link_name))

        # Check that the folder containing the backups does not exist in the
        # backup
        path_to_check = os.path.join(
                    backup_dirname,
                    os.path.relpath(
                        self.backups_container_dirname,
                        self.root_dir.name)
                )
        self.assertFalse(os.path.exists(path_to_check))

        # Check that all other files do
        self._compare_directory_content(
            self.files,
            os.path.join(
                backup_dirname,
                os.path.relpath(self.orig_dirname,self.root_dir.name)
            )
        )

    def tearDown(self):
        # Clean up temporary directory
        self.root_dir.cleanup()
