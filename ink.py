#!/usr/bin/python3

import sys
import os
import traceback
import time
import subprocess
import argparse
import configparser
import datetime
import shutil
from enum import Enum

def run_shell_command(command, error_string = 'Shell command failed.'):
    '''
    Run a shell command given as a list of strings corresponding to the
    arguments. If the command fails, raise a RuntimeError with the
    error string given.
    '''
    # Run shell command
    p = subprocess.Popen(' '.join(command), shell=True)
    p.communicate()

    # Check return code and raise error if command did not succeed
    if p.returncode != 0:
        raise RuntimeError(error_string)

class PartitionManager:
    '''
    A class to manage mounting and unmounting partitions.
    '''

    MountStatus = Enum('MountStatus', 'NEWLY_MOUNTED ALREADY_MOUNTED')

    def __init__(self, mount_point, uuid, label, dev, logfile):
        ''' Initialize with the mount point of the partition and optionally its
        UUID, label or device identifier.'''
        self._mount_point = mount_point
        self._uuid = uuid
        self._label = label
        self._dev = dev
        self._logfile = logfile

    def mount_partition(self):
        '''
        Mount the partition to the mount point specified in the
        constructor. The partition to mount is identified as follows:
            - by UUID, if given
            - by partition label, if given
            - by device identifier, if given
            - if none of the above are given: by entry in /etc/fstab
            - if no entry in /etc/fstab exists: error
        '''
        # Initialize mount status
        self._mount_status = self.MountStatus.ALREADY_MOUNTED

        # Check if a mount point was given
        if len(self._mount_point) == 0:
            self._log('No mount point given. Not mounting a partition.')
        elif self._is_partition_mounted():
            self._log('Partition is already mounted.')
        else:
            self._log('Mounting partition to folder {:s}'.format(
                          self._mount_point))
            # Initialize basic command
            shell_command = ["mount"]

            # Check UUID, label and device in that order
            if len(self._uuid) > 0:
                shell_command.extend(['-U', self._uuid])
            elif len(self._label) > 0:
                shell_command.extend(['-L', self._label])
            elif len(self._dev) > 0:
                shell_command.append(self._dev)

            # Add mount point of partition to shell arguments
            shell_command.append(self._mount_point)

            # Run command
            run_shell_command(shell_command, 'Mounting backup disk failed.')
            self._log('Partition mounted.')

            # Set mount status to newly mounted -- means we should unmount it
            # afterwards
            self._mount_status = self.MountStatus.NEWLY_MOUNTED

    def unmount_partition_if_needed(self):
        '''
        Unmount the partition at the mount point specified in the constructor
        if the partition was not mounted prior to the object being created.
        If the partition was mounted already when the object was created, do
        nothing.
        '''
        # Only unmount if partition was not previously mounted.
        if self._mount_status == self.MountStatus.NEWLY_MOUNTED:
            self._log('Unmounting partition...')
            shell_command = ['umount', self._mount_point]

            # Unmount device
            run_shell_command(shell_command, 'Unmounting backup disk failed.')
            self._log('Unmounting successful.')

    def _is_partition_mounted(self):
        '''
        Return true if the partition is currently mounted in the file system.
        '''
        partition_mounted = False
        # Check mounts file to see if a partition is mounted at the current
        # mount point
        with open('/proc/mounts') as mount_file:
            for line in mount_file:
                __, mount_point, __, flags, __, __ = line.split()
                if mount_point == self._mount_point:
                    partition_mounted = True
                    break

        return partition_mounted

    def _log(self, string, print_time = True):
        '''
        Write string to logfile and print to console. If print_date is True:
        prefix the date and time to the string.
        '''
        pass
        #  if print_time:
            #  self._logfile.write('[{:s}] '.format(
                #  self.get_current_time_formatted()))

        #  self._logfile.write(string + '\n')
        #  print(string)

    def _errlog(self, string, print_time = True):
        '''
        Write error string to logfile and print to console. If print_date is
        True: prefix the date and time to the string.
        '''
        self.log('ERROR: ' + string, print_time)

    @staticmethod
    def _get_current_time_formatted(date_format = '%H:%M:%S'):
        '''
        Return current time, formatted using string date_format.
        '''
        return datetime.datetime.now().strftime(date_format)

class BackupInstance:
    ''' A single instance of a backup generator for a specific
    configuration.'''
    def __init__(self, config, force_backup, logfile):
        ''' Initialize backup instance based on config read from file.'''
        # Check and fix config arguments
        config = self._check_config(config)

        # Set instance name
        self.name = config.name

        # Manager for partition where backups should be created
        self.partition_manager = PartitionManager(
            config.get('mount_point'),
            config.get('UUID'),
            config.get('partition_label'),
            config.get('partition_device'),
            logfile)

        # Backup options
        self.backup_folder = config.get('backup_folder')
        self.to_backup = config.get('to_backup')
        self.backup_type = config.get('backup_type')
        self.exclude_file = config.get('exclude_file')
        self.link_name = config.get('link_name')
        self.folder_prefix = config.get('folder_prefix')
        self.frequency = config.getint('frequency_seconds')
        self.rebase_root = config.getboolean('rebase_root')
        self.force_backup = force_backup
        self._logfile = logfile

    def run(self, last_backup):
        '''
        Run backups. Check if current backups are outdated (or if force option
        was given) and make new backups if necessary.
        '''
        backups_made = False

        # Run only if backup is outdate (needs to be run again) or if the force
        # option was given.
        if self.force_backup or self._backup_outdated(last_backup):
            self._log('Making new backups.')
            # Mount the drive where the backups should go
            self.partition_manager.mount_partition()
            # Make the backups
            try:
                self._make_backups()
                backups_made = True
            except Exception as e:
                self._errlog('An error occurred making the backups.')
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback,
                                          limit=2, file=sys.stdout)
                self._errlog(str(e))

            finally:
                self.partition_manager.unmount_partition_if_needed()

        return backups_made

    def _make_backups(self):
        '''
        Run rsync command to make new backups.
        '''
        if self.backup_type == 'incremental':
            self._make_backups_incremental()
        elif self.backup_type == 'nolinks':
            self._make_backups_nolinks()
        elif self.backup_type == 'snapshot':
            self._make_backups_snapshot()
        elif self.backup_type == 'full':
            self._make_backups_full()
        else:
            self._log('Backup type {:s} not recognized.'.format(
                self.backup_type))

    def _make_backups_incremental(self):
        '''
        Make an incremental backup.
        '''
        # Get basename of backup folder
        new_backup_folder_base = self._get_backup_folder_basename()

        # Get name of actual backup folder
        new_backup_folder = self._get_backup_folder_name(new_backup_folder_base)
        self._log('New backup folder: ' + new_backup_folder)

        # Get name of previous (symlinked) backup folder
        symlink_latest_backup_folder = os.path.join(self.backup_folder,
                                                    self.link_name)

        # Set up rsync command
        shell_command = ['rsync', '-ax']

        # If logfile exists, use it.
        if self._logfile is not None:
            shell_command.extend(['--log-file',
                                  self.logfile])

        # Check if symlink to previous backup exists
        if os.path.isdir(symlink_latest_backup_folder):
            shell_command.append('--link-dest=' + symlink_latest_backup_folder)

        # Check if exclude file given
        if len(self.exclude_file) > 0 and \
                os.path.exists(self.exclude_file):
            shell_command.append('--exclude-from=' + self.exclude_file)

        # Add source and destination
        if self.to_backup == '/':
            shell_command.extend([self.to_backup, new_backup_folder])
        else:
            shell_command.extend([self.to_backup + '/',
                                  new_backup_folder])

        # Run rsync command
        run_shell_command(shell_command)

        # Replace symlink
        self._replace_symlink(symlink_latest_backup_folder,
                              new_backup_folder_base)

        self._log('Backups succeeded.')

    def _make_backups_nolinks(self):
        '''
        Make single, incremental backup with no links based on section_config.
        The new backup folder will contain a full backup, while the previous
        folder will contain only files that were changed between the previous
        and the current backup.
        '''
        # Get basename of backup folder
        new_backup_folder_base = self._get_backup_folder_basename()

        # Get name of actual backup folder
        new_backup_folder = self._get_backup_folder_name(new_backup_folder_base)
        self._log('New backup folder: ' + new_backup_folder)

        # Get name of previous (symlinked) backup folder
        symlink_latest_backup_folder = os.path.join(self.backup_folder,
                                                    self.link_name)

        # Set up rsync command
        shell_command = ['rsync', '-ax']

        # Check if symlink to previous backup exists
        if os.path.isdir(symlink_latest_backup_folder):
            # Add option to make backups of changed files
            shell_command.append('-b')

            # Get name of last backup folder
            previous_backup_folder_base = \
                os.path.realpath(symlink_latest_backup_folder)

            # Remove the new backup folder
            shutil.rmtree(new_backup_folder_base)

            # Move the previous backup folder to the new backup folder
            os.rename(previous_backup_folder_base, new_backup_folder_base)

            # Make a new empty directory matching the previous backup
            # folder base
            previous_backup_folder_base += '_bak'
            os.mkdir(previous_backup_folder_base)

            # Get the actual previous backup folder
            previous_backup_folder = self._get_backup_folder_name(
                previous_backup_folder_base)

            # Add previous backup folder as the backup dir for any deleted
            # files
            shell_command.extend(['--backup-dir', previous_backup_folder])

        # Add exclude and log files
        shell_command = self._add_exclude_and_log_files(shell_command)

        # Add source and destination
        if self.to_backup == '/':
            shell_command.extend([self.to_backup, new_backup_folder])
        else:
            shell_command.extend([self.to_backup + '/',
                                  new_backup_folder])

        # Run rsync command
        run_shell_command(shell_command)

        # Replace symlink
        self._replace_symlink(symlink_latest_backup_folder,
                              new_backup_folder_base)

        self._log('Backups succeeded.')

    def _make_backups_snapshot(self):
        '''
        Make single, snapshot backup. A snapshot backup is an exact replica of
        the directory being backed up, with no separate subdirectories for
        changes made over time.
        '''
        # Get name of actual backup folder
        new_backup_folder = self.backup_folder
        self._log('New backup folder: ' + new_backup_folder)

        # Make sure new backup folder has trailing slash
        if new_backup_folder[-1] != '/':
            new_backup_folder += '/'

        # Set up rsync command
        shell_command = ['rsync', '-ax', '--delete']

        # Add exclude and log files
        shell_command = self._add_exclude_and_log_files(shell_command)

        # Add source and destination
        if self.to_backup == '/':
            shell_command.extend([self.to_backup, new_backup_folder])
        else:
            shell_command.extend([self.to_backup + '/',
                                  new_backup_folder])

        # Run rsync command
        run_shell_command(shell_command)

        self._log('Backups succeeded.')

    def _make_backups_full(self):
        '''
        Make a full copy of the directory being backed up.
        '''
        # Get basename of backup folder
        new_backup_folder_base = self._get_backup_folder_basename(
            )

        # Get name of actual backup folder
        new_backup_folder = self._get_backup_folder_name(new_backup_folder_base)
        self._log('New backup folder: ' + new_backup_folder)

        # Get name of previous (symlinked) backup folder
        symlink_latest_backup_folder = os.path.join(self.backup_folder,
                                                    self.link_name)

        # Set up rsync command
        shell_command = ['rsync', '-ax']

        # Add exclude and log files
        shell_command = self._add_exclude_and_log_files(shell_command)

        # Add source and destination
        if self.to_backup == '/':
            shell_command.extend([self.to_backup, new_backup_folder])
        else:
            shell_command.extend([self.to_backup + '/',
                                  new_backup_folder])

        # Run rsync command
        run_shell_command(shell_command)

        # Replace symlink
        self._replace_symlink(symlink_latest_backup_folder,
                              new_backup_folder_base)

        self._log('Backups succeeded.')

    def _get_backup_folder_basename(self):
        '''
        Get base name of folder to hold new backups and create the folder in
        the file system. This folder will be in the 'backup_folder' directory
        and will have a name based on the current date/time in the system time
        zone using the ISO 8601 format. Name clashes are resolved by appending
        an integer to the end of the folder name.
        '''
        # Get name of new backup folder
        new_backup_folder_base = os.path.join(
            self.backup_folder,
            self.folder_prefix + \
            datetime.datetime.now().strftime('%Y-%m-%dT%H:%M'))

        # Make directory to hold new backup
        n = 0
        while (1):
            if n > 0:
                tmp_folder_name = new_backup_folder_base + '_' + str(n)
            else:
                tmp_folder_name = new_backup_folder_base
            try:
                os.makedirs(tmp_folder_name)
                new_backup_folder_base = tmp_folder_name
                break
            except FileExistsError:
                n = n + 1
                continue

        return new_backup_folder_base

    def _get_backup_folder_name(self, backup_folder_basename):
        '''
        Get full name of folder to hold new backups and create the folder in
        the filesystem.
        '''
        # Check if we should append name of directory to back up to the folder
        # name (such that all backups start with root at /)
        if self.rebase_root:
            if self.to_backup[0] == '/':
                new_backup_folder = os.path.join(
                    backup_folder_basename,
                    self.to_backup[1:])
            else:
                new_backup_folder = os.path.join(
                    backup_folder_basename,
                    self.to_backup)
        else:
            new_backup_folder = backup_folder_basename

        # Make new backup folder
        try:
            os.makedirs(new_backup_folder)
        except FileExistsError:
            pass

        # Make sure new backup folder has a trailing slash
        if new_backup_folder[-1] != '/':
            new_backup_folder = new_backup_folder + '/'

        return new_backup_folder


    @staticmethod
    def _replace_symlink(symlink_latest_backup_folder, new_backup_folder_base):
        '''
        Replace symlink given by symlink_latest_backup_folder with a relative
        link of the same name pointing to new_backup_folder_base.
        '''
        # Replace previous symlink
        try:
            os.unlink(symlink_latest_backup_folder)
        except FileNotFoundError:
            pass

        os.symlink(os.path.relpath(
            os.path.join(new_backup_folder_base),
            os.path.dirname(symlink_latest_backup_folder)),
                   symlink_latest_backup_folder)

    def _add_exclude_and_log_files(self, shell_command):
        '''
        Add arguments for the exclude and logfiles to the rsync command given
        in shell_command.
        '''
        #  If logfile exists, use it.
        #  if self.logfile is not None:
            #  shell_command.extend(['--log-file',
                                  #  section_config.get('logfile')])

        # Check if exclude file given
        if len(self.exclude_file) > 0 and \
                os.path.exists(self.exclude_file):
            shell_command.append('--exclude-from=' + self.exclude_file)

        return shell_command

    @staticmethod
    def _check_config(config):
        '''
        Check the syntax of the config arguments.
        '''
        # Option 'to_backup' must be given
        if len(config.get('to_backup')) == 0:
            raise ValueError("The directory to backup (option 'to_backup') "
                             "must be given.")

        # Check that frequency is an int
        try:
            config.getint('frequency_seconds')
        except ValueError:
            raise ValueError("The frequency of the backups for '{:s}' (option "
                             "'frequency_seconds') was given as '{:s}', "
                             "which is not an int!".format(
                                 config.name, config.get('frequency_seconds')))

        # Set all directory arguments to have no trailing slash
        directory_args = ['mount_point', 'backup_folder', 'to_backup',
                          'link_name']
        for arg in directory_args:
            if len(config[arg]) > 1 and config[arg][-1] == '/':
                config[arg] = config[arg][:-1]

        return config

    def _backup_outdated(self, last_backup):
        '''
        Returns true if the last backup made is outdated.
        '''
        self._log('Checking if backup is outdated...')

        # Check if the last backup is too old
        backup_outdated = (time.time() - last_backup) > \
            self.frequency

        if backup_outdated:
            self._log('Previous backup is outdated. Running new backups.')
        else:
            self._log('Previous backup not outdated. Not running new backups.')

        return backup_outdated

    def _log(self, string, print_time = True):
        '''
        Write string to logfile and print to console. If print_date is True:
        prefix the date and time to the string.
        '''
        pass
        #  if print_time:
            #  self._logfile.write('[{:s}] '.format(
                #  self._get_current_time_formatted()))

        #  self._logfile.write(string + '\n')
        #  print(string)

    def _errlog(self, string, print_time = True):
        '''
        Write error string to logfile and print to console. If print_date is
        True: prefix the date and time to the string.
        '''
        self._log('ERROR: ' + string, print_time)

    @staticmethod
    def _get_current_time_formatted(date_format = '%H:%M:%S'):
        '''
        Return current time, formatted using string date_format.
        '''
        return datetime.datetime.now().strftime(date_format)

class RsyncCommandGenerator:
    ''' A class to generate rsync commands based on backup configuration.'''
    pass

class BackupManager:
    '''
    Class to manage multiple sets of backups based on configuration files.
    '''
    HISTORY_FILENAME = '/var/cache/ink/history'
    LOG_FILENAME = '/var/log/ink/ink.log'
    SYSTEM_CONFIG_FILENAME = '/etc/ink/inkrc'

    def __init__(self, argv):
        '''
        Initialize using command line arguments.
        '''
        # Parse command line arguments
        self.args = self._parse_args(argv)

        # Parse config from config file
        files_to_parse = []
        if len(self.args.config_filename) > 0:
            files_to_parse.append(self.args.config_filename)

        if (self.args.use_system_config):
            files_to_parse.append(self.SYSTEM_CONFIG_FILENAME)

        config = self.parse_config(files_to_parse)

        self.logfile = None

        # Initialize backup instances
        self.backup_instances = []
        for section in config.sections():
            self.backup_instances.append(BackupInstance(config[section],
                                                        self.args.force_backup,
                                                        self.logfile))

        # Make history dir
        self._make_system_directory_if_not_exists(self.HISTORY_FILENAME)

        # Make log dir
        self._make_system_directory_if_not_exists(self.LOG_FILENAME)

    def __enter__(self):
        '''
        Open all resources required to generate backups.
        '''
        # Open log file
        self.logfile = open(self.LOG_FILENAME, 'a')
        return self

    def __exit__(self, error_type, error_value, error_trace):
        '''
        Close all resources.
        '''
        # Close log file
        self.logfile.close()
        return False

    def run(self):
        # Read initial history
        history_writer = configparser.ConfigParser()
        history_writer.read(self.HISTORY_FILENAME)

        # Loop through sections and run backups for each one
        for backup_instance in self.backup_instances:
            # Log which section we're running
            self._log('Date: {:s}'.format(
                self._get_current_time_formatted('%Y-%m-%d')), False)
            self._log('Running section {:s}'.format(backup_instance.name))

            # Run backups
            if backup_instance.run(history_writer.getint(backup_instance.name,
                                                         'last_backup')):
                # If backups were successful, add an entry in the cache file
                history_writer.read_dict({backup_instance.name: {'last_backup':
                                                    int(time.time())}})
        # Write updated history
        with open(self.HISTORY_FILENAME, 'w') as history_file:
            history_writer.write(history_file)

    def _make_system_directory_if_not_exists(self, filename):
        '''
        Make a directory to contain system files (e.g. log or cache) if it does
        not exist. If there is a permission error, log and re-raise. No other
        errors are handled.
        '''
        try:
            os.makedirs(os.path.dirname(filename))
        except FileExistsError:
            pass
        except PermissionError as e:
            self.errlog("Permission denied. Try running as a member of the "
            "group 'ink-users'. Exiting.")
            raise(e)

    @staticmethod
    def _parse_args(argv):
        '''
        Parse command line arguments.
        '''
        parser = argparse.ArgumentParser(description='Make local backups of disk.')
        parser.add_argument('config_filename', default = '', nargs = '?',
                            help='Path to configuration file.')
        parser.add_argument('--ignore-system-config', action='store_false',
                            dest='use_system_config')
        parser.add_argument('-f', dest='force_backup', action='store_true',
                            help='Force backup regardless of time stamp')
        return parser.parse_args(argv)

    @staticmethod
    def parse_config(files_to_parse):
        '''
        Parse config from a config file.
        '''
        parser = configparser.ConfigParser()
        parser.read_dict(BackupManager.get_default_config())
        parser.read(files_to_parse)
        return parser

    @staticmethod
    def get_default_config():
        '''
        Return the default configuration as a dict, to be read using the
        ConfigParser's read_dict function.
        '''
        config = dict()
        config['DEFAULT'] = {'mount_point': '',
                             'backup_folder': '%(mount_point)s',
                             'to_backup': '',
                             'backup_type': 'incremental',
                             'exclude_file': '',
                             'UUID': '',
                             'partition_label': '',
                             'partition_device': '',
                             'link_name': 'current',
                             'folder_prefix': 'backup-',
                             'frequency_seconds': '{:d}'.format(60*60*24),
                             'rebase_root': 'true'
                             };
        return config

    def _log(self, string, print_time = True):
        '''
        Write string to logfile and print to console. If print_date is True:
        prefix the date and time to the string.
        '''
        pass
        #  if print_time:
            #  self.logfile.write('[{:s}] '.format(
                #  self._get_current_time_formatted()))

        #  self.logfile.write(string + '\n')
        #  print(string)

    def _errlog(self, string, print_time = True):
        '''
        Write error string to logfile and print to console. If print_date is
        True: prefix the date and time to the string.
        '''
        self.log('ERROR: ' + string, print_time)

    @staticmethod
    def _get_current_time_formatted(date_format = '%H:%M:%S'):
        '''
        Return current time, formatted using string date_format.
        '''
        return datetime.datetime.now().strftime(date_format)

def main(argv):
    try:
        with BackupManager(argv) as backup_manager:
            backup_manager.run()
    except Exception as e:
        print('Making backups failed.')
        traceback.print_exc()

if __name__ == "__main__":
    main(sys.argv[1:])
