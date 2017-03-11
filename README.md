# Ink
## Introduction
Ink is a tool for managing regular, local backups of a file system.
It uses *rsync* for performing file transfers, though it does not (yet) have support for making backups remotely, as rsync does.

## Usage
Ink is configured using a configuration file with the .ini syntax (see Python's ConfigManager).
The default location for the file is /etc/ink/inkrc, however an additional configuration file can be given as a command line argument.
The options in the configuration file are as follows:

### to\_backup
Directory to backup. Should be an absolute path.
  Default: (none)
  Required: yes

### backup\_folder
The name of the folder where the backups should be made. This should be a path
relative to *mount\_point*. If *mount\_point* is left blank, it should be an
absolute path.
  Default: (none)
  Required: yes

### frequency\_seconds
The frequency at which to make backups, in seconds.
  Default: 64800 (1 day)
  Required: no

### backup\_type
Type of backup to perform. Options are:
- incremental: Incremental backups with hard links to a previous backup. The effect is that the directory structure is that of a full backup, i.e. all files are present, but the disk space required is much lower. This is accomplished by creating new versions only of files which have changed since the previous backup. Unchanged files are not duplicated, but rather hardlinked to their previous version. The space required is therefore that of the changed files plus the links.
- nolinks: Incremental backups with no links to a previous backup. This is similar to *incremental*, however no hardlinks are generated for unchanged files. The result is that the most recent backup is a full backup, with all files in the directory structure, while previous backups contain only files that were changed. While this structure is less convenient than the *incremental* version, it has two advantages. First: no disk space is used to create hardlinks for each backup. For most backups, the disk space required for the links is negligible compared to the space required for changed files. For very large filesystems with few changes between backups, or for very frequent backups, however, it could become significant. Second: if the backups are then synced using a cloud storage program (e.g. Google Drive or Dropbox), the program will not recognize that two separate entries are actually hardlinks to the same file in memory, and will create two copies of the same file on the server, defeating the purpose of creating incremental backups.
- full: Full backups. Every backup is a new copy of the file system.
- snapshot: An exact replica of the file system at the most recent backup, with no previous backups stored.
  Default: incremental
  Required: no

### mount\_point
The directory where the partition containing the backups should be mounted (or
is already mounted). The directory should be relative to the root of the file
system. If no partition should be mounted (i.e. for local backups), this option
should be left blank.
*Caution*: leaving this option blank allows backups to be
made anywhere on the device, and for snapshot backups could lead to data loss
if the *backup\_folder*  is not given correctly.
  Default: (none)
  Required: no

### UUID, partition_label, partition_device
The UUID, label and device identifier of the partition to mount. These
parameters are optional if the partition to mount is specified in /etc/fstab.
If they are given, they are used in this order: UUID, label, device.
  Default: (none)
  Required: no

### folder\_prefix
The prefix given to each backup folder (followed by the time of the backup in
ISO 8601 format). For snapshot backups, this option is ignored.
  Default: backup-
  Required: no

### link\_name
The name given to the symbolic link pointing to the most recent backup. For
snapshot backups, this option is ignored.
  Default: current
  Required: no

### exclude\_file
The name of a file containing the directories to exclude from the backups. By
default, nothing is excluded. If *backup\_folder* is a subdirectory of
*to\_backup* (as is always the case for full disk backups), this file must be
given and must contain *backup\_folder* to avoid an infinite loop,
  Default: (none)
  Required: no

### rsync\_log\_file
The name of a file to write rsync logs. Note that this is not the same as the
log file for ink, which is in /var/log/ink/ink.log.
  Default: (none)
  Required: no

### cross\_filesystems
Equivalent to rsync option -x.
If false, do not cross filesystems when making backups.
That means if a folder inside of *to\_backup* is a mount point for another filesystem (e.g. /boot is mounted within /), it will be ignored in the backup.
This is a safe option to avoid backing up directories in /mnt that should most likely be ignored.
Default: False
Required: No
