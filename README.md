# Ink
## Introduction
Ink is a tool for managing regular, local backups of a file system.
It uses *rsync* for performing file transfers, though it does not (yet) have support for making backups remotely, as rsync does.

## Installation
### Manual Installation
#### Python Module
Ink is implemented in a single Python file that can be used as a script or as a Python module.
The easiest way to install ink is by using the setup.py script provided:
```bash
python setup.py install
```

This script will install the ink module in its default package directory, and will create a wrapper script run-ink in the user's path that calls ink's main function.

#### Configuration File
A sample configuration file is given in config/inkrc-example.
This file should be edited and moved to /etc/ink/inkrc.

#### systemd
For convenience, a systemd service that runs ink using the default system configuration file is provided, along with a corresponding timer that automatically runs ink once per hour (systemd/ink.{service,timer}).
These files should be copied to /etc/systemd/system.
The service can then be started/stopped manually as any systemd service.
To use the automatic timer (similar to a cron job), it must first be enabled:
```bash
systemctl enable ink.timer
```

### Package Managers
#### Pacman
A PKGBUILD is provided in the packages/ directory that installs the python module and wrapper script, copies the systemd files to their respective directories, and moves the sample config file to /etc/ink/inkrc.
To allow ink to run automatically, the systemd timer must still be initialized, as described above.

## Usage
### Configuration File
Ink is configured using a configuration file with the .ini syntax (see Python's ConfigManager).
The default location for the file is /etc/ink/inkrc, however an additional configuration file can be given as a command line argument.
A sample file is provided in config/inkrc-example
The options in the configuration file are as follows:

#### to\_backup
Directory to backup. Should be an absolute path.  
  Default: (none)  
  Required: yes

#### backup\_folder
The name of the folder where the backups should be made. This should be a path
relative to *mount\_point*. If *mount\_point* is left blank, it should be an
absolute path.  
  Default: (none)  
  Required: yes

#### frequency\_seconds
The frequency at which to make backups, in seconds.  
  Default: 64800 (1 day)  
  Required: no

#### backup\_type
Type of backup to perform. Options are:
- incremental: Incremental backups with hard links to a previous backup. The effect is that the directory structure is that of a full backup, i.e. all files are present, but the disk space required is much lower. This is accomplished by creating new versions only of files which have changed since the previous backup. Unchanged files are not duplicated, but rather hardlinked to their previous version. The space required is therefore that of the changed files plus the links.
- nolinks: Incremental backups with no links to a previous backup. This is similar to *incremental*, however no hardlinks are generated for unchanged files. The result is that the most recent backup is a full backup, with all files in the directory structure, while previous backups contain only files that were changed. While this structure is less convenient than the *incremental* version, it has two advantages. First: no disk space is used to create hardlinks for each backup. For most backups, the disk space required for the links is negligible compared to the space required for changed files. For very large filesystems with few changes between backups, or for very frequent backups, however, it could become significant. Second: if the backups are then synced using a cloud storage program (e.g. Google Drive or Dropbox), the program will not recognize that two separate entries are actually hardlinks to the same file in memory, and will create two copies of the same file on the server, defeating the purpose of creating incremental backups.
- full: Full backups. Every backup is a new copy of the file system.
- snapshot: An exact replica of the file system at the most recent backup, with no previous backups stored.

Default: incremental  
Required: no

#### mount\_point
The directory where the partition containing the backups should be mounted (or
is already mounted). The directory should be relative to the root of the file
system. If no partition should be mounted (i.e. for local backups), this option
should be left blank.
*Caution*: leaving this option blank allows backups to be
made anywhere on the device, and for snapshot backups could lead to data loss
if the *backup\_folder*  is not given correctly.  
  Default: (none)  
  Required: no

#### UUID, partition_label, partition_device
The UUID, label and device identifier of the partition to mount. These
parameters are optional if the partition to mount is specified in /etc/fstab.
If they are given, they are used in this order: UUID, label, device.  
  Default: (none)  
  Required: no

#### folder\_prefix
The prefix given to each backup folder (followed by the time of the backup in
ISO 8601 format). For snapshot backups, this option is ignored.  
  Default: backup-  
  Required: no

#### link\_name
The name given to the symbolic link pointing to the most recent backup. For
snapshot backups, this option is ignored.  
  Default: current  
  Required: no

#### exclude\_file
The name of a file containing the directories to exclude from the backups. By
default, only *backup\_folder* is excluded (to avoid infinite recursion).
For a typical full backup (i.e. of the entire filesystem), at least the following should be excluded:
- /mnt/\*
- /dev/\*
- /proc/\*
- /sys/\*
- /tmp/\*
- /run/\*
- /media/\*
- /lost+found

(Note that the directories themselves are not excluded, only their contents.
This facilitates restoring from backups, since the system usually requires those directories to exist at startup.)  

Additionally, any other directories that are backed up separately (e.g. /home) should be excluded as well.
To reduce the space required by the backups, programs which use a lot of disk space but which can be re-downloaded and installed if necessary can also be excluded.
TeXLive is a good candidate to reduce the disk space required.

Default: (none)  
Required: no

#### rsync\_log\_file
The name of a file to write rsync logs. Note that this is not the same as the
log file for ink, which is in /var/log/ink/ink.log.  
  Default: (none)  
  Required: no

#### cross\_filesystems
Equivalent to rsync option -x.
If false, do not cross filesystems when making backups.
That means if a folder inside of *to\_backup* is a mount point for another filesystem (e.g. /boot is mounted within /), it will be ignored in the backup.
This is a safe option to avoid backing up directories in /mnt that should most likely be ignored.  
Default: False  
Required: No

#### date\_format
The format to use for the current date when creating backup folders.
The syntax is the same as that of the ```date``` command (see ```man date``` for details).
Note that the '%' symbols in the date format must escaped by repeating them.  
  Default: %%Y-%%m-%%dT%%H:%%M
  Required: No

### Command-line Arguments
usage: ink.py [-h] [--ignore-system-config] [-f] [config_filename]

Make local backups of disk.

positional arguments:  
  config\_filename       Path to additional configuration file.

optional arguments:  
  -h, --help            show this help message and exit  
  --ignore-system-config  
                        Ignore the system configuration file.  
  -f                    Force backup regardless of time stamp  
