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

class BackupManager:
    HISTORY_FILENAME = '/var/cache/ink/history'
    SYSTEM_CONFIG_FILENAME = '/etc/ink/inkrc'

    MountStatus = Enum('MountStatus', 'NEWLY_MOUNTED ALREADY_MOUNTED')

    def __init__(self, args):
        self.args = args

        # Parse config from config file
        files_to_parse = []
        if len(self.args.config_filename) > 0:
            files_to_parse.append(self.args.config_filename)

        if (self.args.use_system_config):
            files_to_parse.append(self.SYSTEM_CONFIG_FILENAME)

        self.global_config = self.parse_config(files_to_parse)

        self.logfile = None
        self.errfile = None

        # Make history dir
        try:
            os.makedirs(os.path.dirname(self.HISTORY_FILENAME))
        except FileExistsError:
            pass

    def run(self):
        # Read initial history
        history_writer = configparser.ConfigParser()
        history_writer.read(self.HISTORY_FILENAME)

        # Loop through sections and run backups for each one
        for section in self.global_config.sections():
            config_section = self.global_config[section]
            config_section = self.check_config(config_section)

            # Make log and error directories
            try:
                os.makedirs(os.path.dirname(config_section.get('logfile')))
            except FileExistsError:
                pass
            try:
                os.makedirs(os.path.dirname(config_section.get('errfile')))
            except FileExistsError:
                pass

            # Open log and error files
            if len(config_section.get('logfile')) > 0:
                self.logfile = open(config_section.get('logfile'), 'w')

            if (config_section.get('logfile') !=
                    config_section.get('errfile')) and \
                    len(config_section.get('errfile')) > 0:
                self.errfile = open(config_section.get('errfile'), 'w')

            # Log which section we're running
            self.log('Date: {:s}'.format(
                self.get_current_time_formatted('%Y-%m-%d')), False)
            self.log('Running section {:s}'.format(section))

            # Run backups
            if self.run_backups(config_section, self.args):
                # If backups were successful, add an entry in the cache file
                history_writer.read_dict({section: {'last_backup':
                                                    int(time.time())}})
            # Close log and error files
            if self.logfile:
                self.logfile.close()

            if self.errfile:
                self.errfile.close()

        with open(self.HISTORY_FILENAME, 'w') as history_file:
            history_writer.write(history_file)

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
    def check_config(config):
        '''
        Check the syntax of the config arguments.
        '''
        # Option 'to_backup' must be given
        if len(config.get('to_backup')) == 0:
            raise ValueError("The directory to backup (option 'to_backup') must be"
                             " given.")
        # Check that frequency is an int
        try:
            config.getint('frequency_seconds')
        except ValueError:
            raise ValueError("The frequency of the backups for '{:s}' (option "
                             "'frequency_seconds') was given as '{:s}', "
                             "which is not an int!".format(
                                 config.name, config.get('frequency_seconds')))

        # Set all directory arguments to have no trailing slash
        directory_args = ['mount_point', 'backup_folder', 'to_backup', 'link_name']
        for arg in directory_args:
            if config[arg][-1] == '/' and len(config[arg]) > 1:
                config[arg] = config[arg][:-1]

        return config

    @staticmethod
    def get_default_config():
        '''
        Return the default configuration as a dict, to be read using the
        ConfigParser's read_dict function.
        '''
        config = dict()
        config['DEFAULT'] = {'mount_point': '/mnt/backups',
                             'backup_folder': '%(mount_point)s',
                             'to_backup': '',
                             'backup_type': 'incremental',
                             'exclude_file': '',
                             'UUID': '',
                             'partition_label': '',
                             'partition_device': '',
                             'logfile': '/var/log/ink/backups.log',
                             'errfile': '/var/log/ink/backups.err',
                             'link_name': 'current',
                             'folder_prefix': 'backup-',
                             'frequency_seconds': '{:d}'.format(60*60*24)
                             };
        return config

    def log(self, string, print_time = True):
        '''
        Log string to logfile.
        '''
        if self.logfile is not None:
            if print_time:
                self.logfile.write('[{:s}] '.format(
                    self.get_current_time_formatted()))

            self.logfile.write(string + '\n')
        print(string)

    def errlog(self, string, print_time = True):
        '''
        Log string to errfile.
        '''
        if self.errfile is not None:
            if print_time:
                self.logfile.write('[{:s}] '.format(self.get_current_time_formatted()))

            self.errfile.write(string + '\n')
        print(string)

    @staticmethod
    def get_current_time_formatted(date_format = '%H:%M:%S'):
        return datetime.datetime.now().strftime(date_format)

    def run_backups(self, section, args):
        '''
        Run a backup based on a section of the config file corresponding to a
        backup of a single directory.
        '''

        backups_made = False

        # Run only if backup is outdate (needs to be run again) or if the force
        # option was given.
        if args.force_backup or self.backup_outdated(section):
            self.log('Making new backups.')
            # Mount the drive where the backups should go
            try:
                mount_status = self.mount_drive(section)
            except RuntimeError as e:
                self.errlog('Error: ' + str(e))
                self.errlog('Exiting.')
                return False

            # Make the backups
            try:
                self.make_backups(section)
                backups_made = True
            except Exception as e:
                self.errlog('An error occurred making the backups.')
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_exception(exc_type, exc_value, exc_traceback,
                                          limit=2, file=self.logfile)
                traceback.print_exception(exc_type, exc_value, exc_traceback,
                                          limit=2, file=sys.stdout)
                self.errlog(str(e))

            finally:
                # Unmount drive
                if mount_status == self.MountStatus.NEWLY_MOUNTED:
                    try:
                        self.unmount_drive(section)
                    except Exception as e:
                        self.errlog('An error occurred while unmounting the '
                                    'partition.')
                        exc_type, exc_value, exc_traceback = sys.exc_info()
                        traceback.print_exception(exc_type, exc_value, exc_traceback,
                                                  limit=2, file=self.logfile)
                        traceback.print_exception(exc_type, exc_value, exc_traceback,
                                                  limit=2, file=sys.stdout)
                        self.errlog(str(e))

        return backups_made

    def backup_outdated(self, section_config):
        '''
        Return True if the last backup of the directory given in section_config is
        older than the specified frequency.
        '''
        self.log('Checking if backup is outdated...')
        # Read history from cache
        parser = configparser.ConfigParser()
        parser.read('/var/cache/ink/history')

        # Check if there is an entry for the given section
        try:
            section_history = parser[section_config.name]

            # Read epoch time of last backup
            last_backup = section_history.getint('last_backup', 0)
        except KeyError:
            last_backup = 0

        # Check if the last backup is too old
        backup_outdated = (int(time.time()) - last_backup) > \
            section_config.getint('frequency_seconds')

        if backup_outdated:
            self.log('Previous backup is outdated. Running new backups.')
        else:
            self.log('Previous backup not outdated. Not running new backups.')

        return backup_outdated

    def _get_backup_folder_basename(self, section_config):
        '''
        Get base name of folder to hold new backups and create the folder in
        the file system. This folder will be in the 'backup_folder' directory
        and will have a name based on the current date/time in the system time
        zone using the ISO 8601 format. Name clashes are resolved by appending
        an integer to the end of the folder name.
        '''
        # Get name of new backup folder
        new_backup_folder_base = os.path.join(
            section_config.get('backup_folder'),
            section_config.get('folder_prefix') + \
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

    def _get_backup_folder_name(self, section_config, backup_folder_basename):
        '''
        Get full name of folder to hold new backups and create the folder in
        the filesystem.
        '''
        # Append name of directory to back up to the folder name (such that all
        # backups start with root at /)
        if section_config.get('to_backup')[0] == '/':
            self.log(section_config.get('to_backup')[1:])
            new_backup_folder = os.path.join(backup_folder_basename,
                                             section_config.get('to_backup')[1:])
        else:
            new_backup_folder = os.path.join(backup_folder_basename,
                                             section_config.get('to_backup'))

        # Make new backup folder
        try:
            os.makedirs(new_backup_folder)
        except FileExistsError:
            pass

        # Make sure new backup folder has a trailing slash
        if new_backup_folder[-1] != '/':
            new_backup_folder = new_backup_folder + '/'

        return new_backup_folder

    def _run_shell_command(self, shell_command):
        '''
        Run a shell command given as an array of strings representing the
        arguments to the command.
        '''
        # Run shell command
        self.log('Running shell command: ' + ' '.join(shell_command))
        p = subprocess.Popen(' '.join(shell_command), shell=True)
        p.communicate()

        # Check return code and raise error if command did not succeed
        if p.returncode != 0:
            raise RuntimeError('Shell command failed.')

    def _replace_symlink(self, symlink_latest_backup_folder, new_backup_folder_base):
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

    def _add_exclude_and_log_files(self, section_config, shell_command):
        '''
        Add arguments for the exclude and logfiles to the rsync command given
        in shell_command.
        '''
        # If logfile exists, use it.
        if self.logfile is not None:
            shell_command.extend(['--log-file',
                                  section_config.get('logfile')])

        # Check if exclude file given
        if len(section_config.get('exclude_file')) > 0 and \
                os.path.exists(section_config.get('exclude_file')):
            shell_command.append('--exclude-from=' + section_config.get('exclude_file'))

        return shell_command

    def make_backup_incremental(self, section_config):
        '''
        Make single, incremental backup with hard links based on
        section_config.
        '''
        # Get basename of backup folder
        new_backup_folder_base = self._get_backup_folder_basename(
            section_config)

        # Get name of actual backup folder
        new_backup_folder = self._get_backup_folder_name(section_config,
                                                         new_backup_folder_base)
        self.log('New backup folder: ' + new_backup_folder)

        # Get name of previous (symlinked) backup folder
        symlink_latest_backup_folder = os.path.join(section_config.get('backup_folder'),
                                                    section_config.get('link_name'))

        # Set up rsync command
        shell_command = ['rsync', '-ax']

        # If logfile exists, use it.
        if self.logfile is not None:
            shell_command.extend(['--log-file',
                                  section_config.get('logfile')])

        # Check if symlink to previous backup exists
        if os.path.isdir(symlink_latest_backup_folder):
            shell_command.append('--link-dest=' + symlink_latest_backup_folder)

        # Check if exclude file given
        if len(section_config.get('exclude_file')) > 0 and \
                os.path.exists(section_config.get('exclude_file')):
            shell_command.append('--exclude-from=' + section_config.get('exclude_file'))

        # Add source and destination
        if section_config.get('to_backup') == '/':
            shell_command.extend([section_config.get('to_backup'), new_backup_folder])
        else:
            shell_command.extend([section_config.get('to_backup') + '/',
                                  new_backup_folder])

        # Run rsync command
        self._run_shell_command(shell_command)

        # Replace symlink
        self._replace_symlink(symlink_latest_backup_folder,
                              new_backup_folder_base)

        self.log('Backups succeeded.')

    def make_backup_nolinks(self, section_config):
        '''
        Make single, incremental backup with no links based on section_config.
        The new backup folder will contain a full backup, while the previous
        folder will contain only files that were changed between the previous
        and the current backup.
        '''
        # Get basename of backup folder
        new_backup_folder_base = self._get_backup_folder_basename(
            section_config)

        # Get name of actual backup folder
        new_backup_folder = self._get_backup_folder_name(section_config,
                                                         new_backup_folder_base)
        self.log('New backup folder: ' + new_backup_folder)

        # Get name of previous (symlinked) backup folder
        symlink_latest_backup_folder = os.path.join(section_config.get('backup_folder'),
                                                    section_config.get('link_name'))

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
                section_config, previous_backup_folder_base)

            # Add previous backup folder as the backup dir for any deleted
            # files
            shell_command.extend(['--backup-dir', previous_backup_folder])

        # Add exclude and log files
        shell_command = self._add_exclude_and_log_files(section_config,
                                                        shell_command)

        # Add source and destination
        if section_config.get('to_backup') == '/':
            shell_command.extend([section_config.get('to_backup'), new_backup_folder])
        else:
            shell_command.extend([section_config.get('to_backup') + '/',
                                  new_backup_folder])

        # Run rsync command
        self._run_shell_command(shell_command)

        # Replace symlink
        self._replace_symlink(symlink_latest_backup_folder,
                              new_backup_folder_base)

        self.log('Backups succeeded.')

    def make_backup_snapshot(self, section_config):
        '''
        Make single, snapshot backup. A snapshot backup is an exact replica of
        the directory being backed up, with no separate subdirectories for
        changes made over time.
        '''
        # Get name of actual backup folder
        new_backup_folder = section_config.get('backup_folder')
        self.log('New backup folder: ' + new_backup_folder)

        # Make sure new backup folder has trailing slash
        if new_backup_folder[-1] != '/':
            new_backup_folder += '/'

        # Set up rsync command
        shell_command = ['rsync', '-ax', '--delete']

        # Add exclude and log files
        shell_command = self._add_exclude_and_log_files(section_config,
                                                        shell_command)

        # Add source and destination
        if section_config.get('to_backup') == '/':
            shell_command.extend([section_config.get('to_backup'), new_backup_folder])
        else:
            shell_command.extend([section_config.get('to_backup') + '/',
                                  new_backup_folder])

        # Run rsync command
        self._run_shell_command(shell_command)

        self.log('Backups succeeded.')

    def make_backup_full(self, section_config):
        '''
        Make a full copy of the directory being backed up.
        '''
        # Get basename of backup folder
        new_backup_folder_base = self._get_backup_folder_basename(
            section_config)

        # Get name of actual backup folder
        new_backup_folder = self._get_backup_folder_name(section_config,
                                                         new_backup_folder_base)
        self.log('New backup folder: ' + new_backup_folder)

        # Get name of previous (symlinked) backup folder
        symlink_latest_backup_folder = os.path.join(section_config.get('backup_folder'),
                                                    section_config.get('link_name'))

        # Set up rsync command
        shell_command = ['rsync', '-ax']

        # Add exclude and log files
        shell_command = self._add_exclude_and_log_files(section_config,
                                                        shell_command)

        # Add source and destination
        if section_config.get('to_backup') == '/':
            shell_command.extend([section_config.get('to_backup'), new_backup_folder])
        else:
            shell_command.extend([section_config.get('to_backup') + '/',
                                  new_backup_folder])

        # Run rsync command
        self._run_shell_command(shell_command)

        # Replace symlink
        self._replace_symlink(symlink_latest_backup_folder,
                              new_backup_folder_base)

        self.log('Backups succeeded.')

    def make_backups(self, section_config):
        if section_config.get('backup_type') == 'incremental':
            self.make_backup_incremental(section_config)
        elif section_config.get('backup_type') == 'nolinks':
            self.make_backup_nolinks(section_config)
        elif section_config.get('backup_type') == 'snapshot':
            self.make_backup_snapshot(section_config)
        elif section_config.get('backup_type') == 'full':
            self.make_backup_full(section_config)
        else:
            self.log('Backup type {:s} not recognized.'.format(
                section_config.get('backup_type')))

    def unmount_drive(self, section):
        '''
        Unmount the partition where backups were made.
        '''
        self.log('Unmounting partition...')
        shell_command = ['umount', section.get('mount_point')]

        # Unmount device
        p = subprocess.Popen(' '.join(shell_command), shell=True)
        p.communicate()

        # Check return code and raise error if command did not succeed
        if p.returncode != 0:
            raise RuntimeError('Unmounting backup disk failed.')

        self.log('Unmounting successful.')

    def mount_drive(self, section):
        '''
        Mount the partition where the backups should be made.
        '''
        self.log('Checking if partition is already mounted...')

        if not self.is_mounted(section.get('mount_point')):
            self.log('Partition not already mounted. Trying to mount it.')

            # Initialize basic command
            shell_command = ["mount"]

            # Check UUID, label and device in that order
            if len(section.get('UUID')) > 0:
                shell_command.extend(['-U', section.get('UUID')])
            elif len(section.get('partition_label')) > 0:
                shell_command.extend(['-L', section.get('partition_label')])
            elif len(section.get('partition_device')) > 0:
                shell_command.append(section.get('partition_device'))

            # Add mount point of partition to shell arguments
            shell_command.append(section.get('mount_point'))

            # Mount device
            p = subprocess.Popen(' '.join(shell_command), shell=True)
            p.communicate()

            # Check return code and raise error if command did not succeed
            if p.returncode != 0:
                raise RuntimeError('Mounting backup disk failed.')

            self.log('Partition mounted.')
            return self.MountStatus.NEWLY_MOUNTED
        else:
            self.log('Partition already mounted.')
            return self.MountStatus.ALREADY_MOUNTED

    @staticmethod
    def is_mounted(desired_mount_point):
        partition_mounted = False
        with open('/proc/mounts') as mount_file:
            for line in mount_file:
                __, mount_point, __, flags, __, __ = line.split()
                if mount_point == desired_mount_point:
                    partition_mounted = True
                    break

        return partition_mounted

def main():
    args = parse_args(sys.argv[1:])
    backup_manager = BackupManager(args)
    backup_manager.run()

def parse_args(argv):
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

if __name__ == "__main__":
    main()
