#!/usr/bin/env python3

"""
ccf/one_subject_job_submitter.py: Abstract base class for an object
that submits jobs for a pipeline for one subject.
"""

# import of built-in modules
import abc
import contextlib
import logging
import os
import shutil
import stat
import subprocess
import time

# import of third-party modules

# import of local modules
import ccf.processing_stage as ccf_processing_stage
import utils.debug_utils as debug_utils
import utils.delete_resource as delete_resource
import utils.file_utils as file_utils
import utils.os_utils as os_utils
import utils.str_utils as str_utils
import ccf.subject as ccf_subject

# authorship information
__author__ = "Timothy B. Brown"
__copyright__ = "Copyright 2020, The Connectome Coordination Facility (CCF)"
__maintainer__ = "Junil Chang"

# create a module logger
module_logger = logging.getLogger(__name__)
module_logger.setLevel(logging.WARNING)  # Note: This can be overidden by log file configuration


class OneSubjectJobSubmitter(abc.ABC):
	"""
	This class is an abstract base class for classes that are used to submit jobs
	for one pipeline for one subject.
	"""

	def __init__(self, archive, build_home):
		"""
		Initialize a OneSubjectJobSubmitter
		"""
		self._archive = archive
		self._build_home = build_home

		self._xnat_pbs_jobs_home = os_utils.getenv_required('XNAT_PBS_JOBS')
		self._log_dir = os_utils.getenv_required('XNAT_PBS_JOBS_LOG_DIR')

		self._scan = None
		self._working_directory_name_prefix = None

	def processing_stage_from_string(self, str_value):
		return ccf_processing_stage.ProcessingStage.from_string(str_value)

	@property
	def PAAP_POSITIVE_DIR(self):
		return "PA"

	@property
	def PAAP_NEGATIVE_DIR(self):
		return "AP"

	@property
	def RLLR_POSITIVE_DIR(self):
		return "RL"

	@property
	def RLLR_NEGATIVE_DIR(self):
		return "LR"

	@property
	@abc.abstractmethod
	def PIPELINE_NAME(self):
		raise NotImplementedError()

	@property
	def archive(self):
		"""
		The archive with which this submitter is to work.
		"""
		return self._archive

	@property
	def build_home(self):
		"""
		The temporary (e.g. build space) root directory.
		"""
		return self._build_home

	@property
	def xnat_pbs_jobs_home(self):
		"""
		The home directory for the XNAT PBS job scripts.
		"""
		return self._xnat_pbs_jobs_home

	@property
	def log_dir(self):
		"""
		The directory in which to place PUT logs.
		"""
		return self._log_dir

	@property
	def username(self):
		return self._username

	@username.setter
	def username(self, value):
		self._username = value
		module_logger.debug(debug_utils.get_name() + ": set to: " + str(value))

	@property
	def password(self):
		return self._password

	@password.setter
	def password(self, value):
		self._password = value

	@property
	def server(self):
		return self._server

	@server.setter
	def server(self, value):
		self._server = value
		module_logger.debug(debug_utils.get_name() + ": set to " + str(self._server))

	@property
	def project(self):
		return self._project

	@project.setter
	def project(self, value):
		self._project = value
		module_logger.debug(debug_utils.get_name() + ": set to " + str(self._project))

	@property
	def subject(self):
		return self._subject

	@subject.setter
	def subject(self, value):
		self._subject = value
		module_logger.debug(debug_utils.get_name() + ": set to " + str(self._subject))

	@property
	def session(self):
		return self._session

	@session.setter
	def session(self, value):
		self._session = value
		module_logger.debug(debug_utils.get_name() + ": set to " + str(self._session))

	@property
	def classifier(self):
		return self._classifier

	@classifier.setter
	def classifier(self, value):
		self._classifier = value
		module_logger.debug(debug_utils.get_name() + ": set to " + str(self._classifier))

	@property
	def scan(self):
		return self._scan

	@scan.setter
	def scan(self, value):
		self._scan = value
		module_logger.debug(debug_utils.get_name() + ": set to " + str(self._scan))

	@property
	def clean_output_resource_first(self):
		return self._clean_output_resource_first

	@clean_output_resource_first.setter
	def clean_output_resource_first(self, value):
		self._clean_output_resource_first = value
		module_logger.debug(debug_utils.get_name() + ": set to " + str(self._clean_output_resource_first))

	@property
	def put_server(self):
		return self._put_server

	@put_server.setter
	def put_server(self, value):
		self._put_server = value
		module_logger.debug(debug_utils.get_name() + ": set to " + str(self._put_server))

	@property
	def walltime_limit_hours(self):
		return self._walltime_limit_hours

	@walltime_limit_hours.setter
	def walltime_limit_hours(self, value):
		self._walltime_limit_hours = value
		module_logger.debug(debug_utils.get_name() + ": set to " + str(value))

	@property
	def vmem_limit_gbs(self):
		return self._vmem_limit_gbs

	@vmem_limit_gbs.setter
	def vmem_limit_gbs(self, value):
		self._vmem_limit_gbs = value
		module_logger.debug(debug_utils.get_name() + ": set to " + str(value))

	@property
	def mem_limit_gbs(self):
		return self._mem_limit_gbs

	@mem_limit_gbs.setter
	def mem_limit_gbs(self, value):
		self._mem_limit_gbs = value
		module_logger.debug(debug_utils.get_name() + ": set to " + str(value))
		
	@property
	def output_resource_suffix(self):
		return self._output_resource_suffix

	@output_resource_suffix.setter
	def output_resource_suffix(self, value):
		self._output_resource_suffix = value
		module_logger.debug(debug_utils.get_name() + ": set to " + str(value))

	@property
	def output_resource_name(self):
		if self.scan:
			name = self.scan + '_' + self.output_resource_suffix
		else:
			name = self.output_resource_suffix
		return name
	
	@property
	def working_directory_name_prefix(self):
		# Since the working directory name prefix contains a timestamp, it is
		# important to only build the working directory name prefix one time.
		# The first time it is requested, self._working_directory_name_prefix
		# will have a value of None. In that case, build the name, store
		# it and return it. For any subsequent requests, simply return
		# the previously built name.
		if self._working_directory_name_prefix is None:
			current_seconds_since_epoch = int(time.time())
			wdir = self.build_home
			wdir += os.sep + self.project
			wdir += os.sep + self.PIPELINE_NAME
			wdir += '.' + self.subject
			wdir += '_' + self.classifier
			if self.scan:
				wdir += '_' + self.scan
			wdir += '.' + str(current_seconds_since_epoch)
			self._working_directory_name_prefix = wdir

		return self._working_directory_name_prefix

	@property
	def working_directory_name(self):
		return self.working_directory_name_prefix + '.XNAT_PROCESS_DATA'
		
	@property
	def check_data_directory_name(self):
		"""
		Directory in which the check data job script will reside
		"""
		return self.working_directory_name_prefix + '.XNAT_CHECK_DATA'
	
	@property
	def mark_completion_directory_name(self):
		"""
		Directory in which the mark completion job script will reside
		"""
		return self.working_directory_name_prefix + '.XNAT_MARK_COMPLETE_RUNNING_STATUS'
	
	@property
	def scripts_start_name(self):
		start_name = self.working_directory_name
		start_name += os.sep + self.subject
		start_name += '_' + self.classifier
		if self.scan:
			start_name += '_' + self.scan
		start_name += '.' + self.PIPELINE_NAME
		return start_name

	@property
	def processing_info_directory_name(self):
		processing_info_name = self.working_directory_name
		processing_info_name += os.path.sep + self.subject + '_' + self.classifier
		processing_info_name += os.path.sep + 'ProcessingInfo'
		return processing_info_name 	
		
	@property
	def get_data_job_script_name(self):
		"""Name of the script to be submitted to perform the get data job"""
		module_logger.debug(debug_utils.get_name())
		return self.scripts_start_name + '.XNAT_GET_DATA_job.sh'

	def _write_bash_header(self, script):
		bash_line = '#PBS -S /bin/bash'
		file_utils.wl(script, bash_line)
		file_utils.wl(script, '')

	@property
	def get_data_program_path(self):
		"""Path to the program that can get the appropriate data for this processing"""
		name = self.xnat_pbs_jobs_home
		name += os.sep + self.PIPELINE_NAME
		name += os.sep + self.PIPELINE_NAME + '.XNAT_GET'
		return name

	def _get_xnat_pbs_setup_script_path(self):
		xnat_pbs_setup_path = os_utils.getenv_required('XNAT_PBS_JOBS_CONTROL')+ '/xnat_pbs_setup'
		return xnat_pbs_setup_path
			
	def _get_xnat_pbs_setup_script_singularity_version(self):
		xnat_pbs_setup_singularity_version = os_utils.getenv_required('SINGULARITY_CONTAINER_VERSION')
		return xnat_pbs_setup_singularity_version

	def _get_xnat_pbs_setup_script_singularity_container_path(self):
		xnat_pbs_setup_singularity_container = os_utils.getenv_required('SINGULARITY_CONTAINER_PATH')
		return xnat_pbs_setup_singularity_container
		
	def _get_xnat_pbs_setup_script_singularity_container_xnat_path(self):
		xnat_pbs_setup_singularity_container_xnat = os_utils.getenv_required('SINGULARITY_CONTAINER_XNAT_PATH')
		return xnat_pbs_setup_singularity_container_xnat
		
	def _get_xnat_pbs_setup_script_singularity_bind_path(self):
		xnat_pbs_setup_singularity_bind = os_utils.getenv_required('SINGULARITY_BIND_PATH')
		return xnat_pbs_setup_singularity_bind
	
	def _get_xnat_pbs_setup_script_singularity_qunexrun_path(self):
		xnat_pbs_setup_singularity_qunexrun_path = os_utils.getenv_required('SINGULARITY_QUNEXRUN_PATH')
		return xnat_pbs_setup_singularity_qunexrun_path
		
	def _get_xnat_pbs_setup_script_singularity_qunexparameter_path(self):
		xnat_pbs_setup_singularity_qunexparameter_path = os_utils.getenv_required('SINGULARITY_QUNEXPARAMETER_PATH')
		return xnat_pbs_setup_singularity_qunexparameter_path
	
	def _get_xnat_pbs_setup_script_gradient_coefficient_path(self):
		xnat_pbs_setup_gradient_coefficient = os_utils.getenv_required('GRADIENT_COEFFICIENT_PATH')
		return xnat_pbs_setup_gradient_coefficient

	def _get_xnat_pbs_setup_script_freesurfer_license_path(self):
		xnat_pbs_setup_freesurfer_license = os_utils.getenv_required('FREESURFER_LICENSE_PATH')
		return xnat_pbs_setup_freesurfer_license	
	
	def _get_xnat_pbs_setup_script_archive_root(self):
		xnat_pbs_setup_archive_root = os_utils.getenv_required('XNAT_PBS_JOBS_ARCHIVE_ROOT')
		return xnat_pbs_setup_archive_root
	
	def _get_db_name(self): 
		xnat_server = os_utils.getenv_required('REQUESTED_XNAT_SERVER')
		return xnat_server
	
	def create_get_data_job_script(self):
		"""Create the script to be submitted to perform the get data job"""
		module_logger.debug(debug_utils.get_name())

		script_name = self.get_data_job_script_name

		with contextlib.suppress(FileNotFoundError):
			os.remove(script_name)

		script = open(script_name, 'w')
		self._write_bash_header(script)
		script.write('#PBS -l nodes=1:ppn=1,walltime=4:00:00,mem=4gb' + os.linesep)
		script.write('#PBS -o ' + self.working_directory_name + os.linesep)
		script.write('#PBS -e ' + self.working_directory_name + os.linesep)
		script.write(os.linesep)
		script.write('source ' + self._get_xnat_pbs_setup_script_path() + ' ' + self._get_db_name() + os.linesep)
		script.write('module load ' + self._get_xnat_pbs_setup_script_singularity_version()  + os.linesep)
		script.write(os.linesep)
		script.write('singularity exec -B ' + self._get_xnat_pbs_setup_script_archive_root() + ',' + self._get_xnat_pbs_setup_script_singularity_bind_path() + ' ' + self._get_xnat_pbs_setup_script_singularity_container_xnat_path() + ' ' + self.get_data_program_path + ' \\' + os.linesep)
		script.write('  --project=' + self.project + ' \\' + os.linesep)
		script.write('  --subject=' + self.subject + ' \\' + os.linesep)
		script.write('  --classifier=' + self.classifier + ' \\' + os.linesep)
		if self.scan:
			script.write('  --scan=' + self.scan + ' \\' + os.linesep)			
		script.write('  --working-dir=' + self.working_directory_name + os.linesep)
		script.close()
		os.chmod(script_name, stat.S_IRWXU | stat.S_IRWXG)

	@property
	def put_data_script_name(self):
		module_logger.debug(debug_utils.get_name())
		return self.scripts_start_name + '.XNAT_PUT_DATA_job.sh'

	def create_put_data_script(self):
		module_logger.debug(debug_utils.get_name())

		script_name = self.put_data_script_name

		with contextlib.suppress(FileNotFoundError):
			os.remove(script_name)

		script = open(script_name, 'w')
		script.write('#PBS -l nodes=1:ppn=1,walltime=4:00:00,mem=12gb' + os.linesep)
		script.write('#PBS -o ' + self.log_dir + os.linesep)
		script.write('#PBS -e ' + self.log_dir + os.linesep)
		script.write(os.linesep)
		script.write('source ' + self._get_xnat_pbs_setup_script_path() + ' ' + self._get_db_name() + os.linesep)
		script.write('module load ' + self._get_xnat_pbs_setup_script_singularity_version() + os.linesep)
		script.write(os.linesep)
		script.write('mv ' + self.working_directory_name + os.path.sep + '*' + self.PIPELINE_NAME + '* ' + self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + 'ProcessingInfo' + os.linesep)
		script.write(os.linesep)
		script.write('singularity exec -B ' + self._get_xnat_pbs_setup_script_archive_root() + ',' + self._get_xnat_pbs_setup_script_singularity_bind_path() + ' ' + self._get_xnat_pbs_setup_script_singularity_container_xnat_path() + ' ' + self.xnat_pbs_jobs_home + os.sep + 'WorkingDirPut' + os.sep + 'XNAT_working_dir_put.sh \\' + os.linesep)
		script.write('  --leave-subject-id-level \\' + os.linesep)
		script.write('  --user="' + self.username + '" \\' + os.linesep)
		script.write('  --password="' + self.password + '" \\' + os.linesep)
		script.write('  --server="' + str_utils.get_server_name(self.put_server) + '" \\' + os.linesep)
		script.write('  --project="' + self.project + '" \\' + os.linesep)
		script.write('  --subject="' + self.subject + '" \\' + os.linesep)
		script.write('  --session="' + self.session + '" \\' + os.linesep)
		script.write('  --working-dir="' + self.working_directory_name + '" \\' + os.linesep)
		if self.scan:
			script.write('  --scan="' + self.scan + '" \\' + os.linesep)
			script.write('  --resource-suffix="' + self.output_resource_suffix + '" \\' + os.linesep)
		else:
			script.write('  --resource-suffix="' + self.output_resource_name + '" \\' + os.linesep)	
		script.write('  --reason="' + self.PIPELINE_NAME + '"' + os.linesep)
		script.close()
		os.chmod(script_name, stat.S_IRWXU | stat.S_IRWXG)

	@property
	def clean_data_script_name(self):
		module_logger.debug(debug_utils.get_name())
		return self.scripts_start_name + '.CLEAN_DATA_job.sh'

	@property
	def starttime_file_name(self):
		module_logger.debug(debug_utils.get_name())
		starttime_file_name = self.working_directory_name
		starttime_file_name += os.path.sep
		
		starttime_file_name += self.subject + '_' + self.classifier
		starttime_file_name += os.path.sep
		starttime_file_name +='ProcessingInfo'
		starttime_file_name += os.path.sep
		starttime_file_name += self.subject
		starttime_file_name += '_' + self.classifier
		if self.scan:
			starttime_file_name += '_' + self.scan
		starttime_file_name += '.' + self.PIPELINE_NAME
		starttime_file_name += '.starttime'
		return starttime_file_name

	def create_clean_data_script(self):
		module_logger.debug(debug_utils.get_name())

		script_name = self.clean_data_script_name

		with contextlib.suppress(FileNotFoundError):
			os.remove(script_name)

		script = open(script_name, 'w')

		self._write_bash_header(script)
		script.write('#PBS -l nodes=1:ppn=1,walltime=4:00:00,mem=4gb' + os.linesep)
		script.write('#PBS -o ' + self.working_directory_name + os.linesep)
		script.write('#PBS -e ' + self.working_directory_name + os.linesep)
		script.write(os.linesep)
		script.write('mv ' + self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + 'MNINonLinear ')
		script.write(self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.linesep)
		script.write('mv ' + self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + 'T*w ')
		script.write(self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.linesep)
		script.write('mv ' + self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + 'subjects' + os.path.sep + 'specs ')
		script.write(self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + 'ProcessingInfo' + os.linesep)
		script.write('mv ' + self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + 'processing ')
		script.write(self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + 'ProcessingInfo' + os.linesep)
		script.write('mv ' + self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + 'info' + os.path.sep + 'hcpls ')
		script.write(self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + 'ProcessingInfo' + os.linesep)
		script.write('mv ' + self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + 'subjects' + os.path.sep + self.subject + '_' + self.classifier + os.path.sep  + 'subject_hcp.txt ')
		script.write(self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + 'ProcessingInfo' + os.path.sep + 'processing' + os.linesep)
		script.write('mv ' + self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + 'subjects' + os.path.sep + self.subject + '_' + self.classifier + os.path.sep  + 'hcpls' + os.path.sep  + 'hcpls2nii.log ')
		script.write(self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + 'ProcessingInfo' + os.path.sep + 'processing' + os.linesep)
		script.write('find ' + self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier)
		script.write(' -not -path "' + self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + 'T*w/*"')
		script.write(' -not -path "' + self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + 'ProcessingInfo/*"')
		script.write(' -not -path "' + self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.path.sep + 'MNINonLinear/*"')
		script.write(' -delete')
		script.write(os.linesep)
		script.write('echo "Removing any XNAT catalog files still around."' + os.linesep)
		script.write('find ' + self.working_directory_name + ' -name "*_catalog.xml" -delete')
		script.write(os.linesep)
		script.write('echo "Remaining files:"' + os.linesep)
		script.write('find ' + self.working_directory_name + os.path.sep + self.subject + '_' + self.classifier + os.linesep)
		script.close()
		os.chmod(script_name, stat.S_IRWXU | stat.S_IRWXG)

	@property
	def process_data_job_script_name(self):
		"""
		Name of script to be submitted as a job to perform the processing of the data.
		"""
		module_logger.debug(debug_utils.get_name())
		return self.scripts_start_name + '.PROCESS_DATA_job.sh'

	@property
	def setup_file_name(self):
		module_logger.debug(debug_utils.get_name())
		return self.scripts_start_name + '.SETUP.sh'

	@property
	def check_data_job_script_name(self):
		"""
		Name of script to be submitted as a job to perform the check data functionality.
		"""	
		module_logger.debug(debug_utils.get_name())
		name = self.check_data_directory_name
		name += os.sep + self.subject
		name += '_'  + self.classifier
		if self.scan:
			name += '_' + self.scan
		name += '.' + self.PIPELINE_NAME
		name += '.' + 'XNAT_CHECK_DATA_job.sh'
		return name

	@property
	def check_data_program_path(self):
		"""
		Path to program in the XNAT_PBS_JOBS that performs the actual check of result data.
		"""
		name = self.xnat_pbs_jobs_home
		name += os.sep + self.PIPELINE_NAME
		name += os.sep + self.PIPELINE_NAME + '.XNAT_CHECK'
		return name
	
	def create_check_data_job_script(self):
		"""
		Create the script to be submitted as a job to perform the check data functionality.
		"""
		module_logger.debug(debug_utils.get_name())

		script_name = self.check_data_job_script_name

		with contextlib.suppress(FileNotFoundError):
			os.remove(script_name)

		script = open(script_name, 'w')
		self._write_bash_header(script)
		script.write('#PBS -l nodes=1:ppn=1,walltime=4:00:00,mem=4gb' + os.linesep)
		script.write('#PBS -o ' + self.log_dir + os.linesep)
		script.write('#PBS -e ' + self.log_dir + os.linesep)
		script.write(os.linesep)
		script.write('source ' + self._get_xnat_pbs_setup_script_path() + ' ' + self._get_db_name() + os.linesep)
		script.write('module load ' + self._get_xnat_pbs_setup_script_singularity_version() + os.linesep)
		script.write(os.linesep)
		script.write('singularity exec -B ' + self._get_xnat_pbs_setup_script_archive_root() + ',' + self._get_xnat_pbs_setup_script_singularity_bind_path() + ' ' + self._get_xnat_pbs_setup_script_singularity_container_xnat_path() + ' ' + self.check_data_program_path  + ' \\' + os.linesep)
		script.write('  --user="' + self.username + '" \\' + os.linesep)
		script.write('  --password="' + self.password + '" \\' + os.linesep)
		script.write('  --server="' + str_utils.get_server_name(self.put_server) + '" \\' + os.linesep)
		script.write('  --project=' + self.project + ' \\' + os.linesep)
		script.write('  --subject=' + self.subject + ' \\' + os.linesep)
		script.write('  --classifier=' + self.classifier + ' \\' + os.linesep)
		if self.scan:
			script.write('  --scan=' + self.scan + ' \\' + os.linesep)
		elif self.PIPELINE_NAME=='StructuralPreprocessing':
			subject_info = ccf_subject.SubjectInfo(self.project, self.subject, self.classifier)
			fieldmap_type_line = '  --fieldmap=' + 'NONE' 
			script.write(fieldmap_type_line + ' \\' + os.linesep)
		script.write('  --working-dir=' + self.check_data_directory_name + os.linesep)
		script.close()
		os.chmod(script_name, stat.S_IRWXU | stat.S_IRWXG)
		
	@property
	def mark_no_longer_running_script_name(self):
		module_logger.debug(debug_utils.get_name())
		name = self.mark_completion_directory_name
		name += os.sep + self.subject
		name += '_' + self.classifier
		if self.scan:
			name += '_' + self.scan
		name += '.' + self.PIPELINE_NAME
		name += '.' + 'MARK_COMPLETE_RUNNING_STATUS_job.sh'	
		return name

	@property
	def mark_running_status_program_path(self):
		"""
		Path to program in XNAT_PBS_JOS that performs the mark of running status.
		"""
		name = self.xnat_pbs_jobs_home
		name += os.sep + self.PIPELINE_NAME
		name += os.sep + self.PIPELINE_NAME + '.XNAT_MARK_RUNNING_STATUS'
		return name
	
	def create_mark_no_longer_running_script(self):
		module_logger.debug(debug_utils.get_name())

		script_name = self.mark_no_longer_running_script_name

		with contextlib.suppress(FileNotFoundError):
			os.remove(script_name)

		script = open(script_name, 'w')
		self._write_bash_header(script)
		script.write('#PBS -l nodes=1:ppn=1,walltime=4:00:00,mem=4gb' + os.linesep)
		script.write('#PBS -o ' + self.log_dir + os.linesep)
		script.write('#PBS -e ' + self.log_dir + os.linesep)
		script.write(os.linesep)
		script.write('source ' + self._get_xnat_pbs_setup_script_path() + ' ' + self._get_db_name() + os.linesep)
		script.write('module load ' + self._get_xnat_pbs_setup_script_singularity_version()  + os.linesep)
		script.write(os.linesep)
		script.write('singularity exec -B ' + self._get_xnat_pbs_setup_script_archive_root() + ',' + self._get_xnat_pbs_setup_script_singularity_bind_path() + ' ' + self._get_xnat_pbs_setup_script_singularity_container_xnat_path() + ' ' + self.mark_running_status_program_path   + ' \\' + os.linesep)
		script.write('  --user="' + self.username + '" \\' + os.linesep)
		script.write('  --password="' + self.password + '" \\' + os.linesep)
		script.write('  --server="' + str_utils.get_server_name(self.put_server) + '" \\' + os.linesep)
		script.write('  --project="' + self.project + '" \\' + os.linesep)
		script.write('  --subject="' + self.subject + '" \\' + os.linesep)
		script.write('  --classifier="' + self.classifier + '" \\' + os.linesep)
		if self.scan:
			script.write('  --scan="' + self.scan + '" \\' + os.linesep)
		script.write('  --resource="' + 'RunningStatus' + '" \\' + os.linesep)
		script.write('  --done' + os.linesep)
		script.write(os.linesep)
		script.write("rm -rf " + self.mark_completion_directory_name)
		script.close()
		os.chmod(script_name, stat.S_IRWXU | stat.S_IRWXG)
			
	def submit_get_data_jobs(self, stage, prior_job=None):
		module_logger.debug(debug_utils.get_name())

		if stage >= ccf_processing_stage.ProcessingStage.GET_DATA:
			if prior_job:
				get_data_submit_cmd = 'qsub -W depend=afterok:' + prior_job + ' ' + self.get_data_job_script_name
			else:
				get_data_submit_cmd = 'qsub ' + self.get_data_job_script_name

			completed_submit_process = subprocess.run(
				get_data_submit_cmd, shell=True, check=True, stdout=subprocess.PIPE, universal_newlines=True)
			get_data_job_no = str_utils.remove_ending_new_lines(completed_submit_process.stdout)
			return get_data_job_no, [get_data_job_no]

		else:
			module_logger.info("Get data job not submitted")
			return None, None

	def submit_process_data_jobs(self, stage, prior_job=None):
		module_logger.debug(debug_utils.get_name())

		if stage >= ccf_processing_stage.ProcessingStage.PROCESS_DATA:
			if prior_job:
				work_submit_cmd = 'qsub -W depend=afterok:' + prior_job + ' ' + self.process_data_job_script_name
			else:
				work_submit_cmd = 'qsub ' + self.process_data_job_script_name

			completed_submit_process = subprocess.run(
				work_submit_cmd, shell=True, check=True, stdout=subprocess.PIPE, universal_newlines=True)
			work_job_no = str_utils.remove_ending_new_lines(completed_submit_process.stdout)
			return work_job_no, [work_job_no]

		else:
			module_logger.info("Process data job not submitted")
			return None, None

	def submit_clean_data_jobs(self, stage, prior_job=None):
		module_logger.debug(debug_utils.get_name())

		if stage >= ccf_processing_stage.ProcessingStage.CLEAN_DATA:
			if prior_job:
				clean_submit_cmd = 'qsub -W depend=afterok:' + prior_job + ' ' + self.clean_data_script_name
			else:
				clean_submit_cmd = 'qsub ' + self.clean_data_script_name

			completed_submit_process = subprocess.run(
				clean_submit_cmd, shell=True, check=True, stdout=subprocess.PIPE, universal_newlines=True)
			clean_job_no = str_utils.remove_ending_new_lines(completed_submit_process.stdout)
			return clean_job_no, [clean_job_no]

		else:
			module_logger.info("Clean data job not submitted")
			return None, None

	def submit_put_data_jobs(self, stage, prior_job=None):
		module_logger.debug(debug_utils.get_name())

		if stage >= ccf_processing_stage.ProcessingStage.PUT_DATA:
			if prior_job:
				put_submit_cmd = 'qsub -W depend=afterok:' + prior_job + ' ' + self.put_data_script_name
			else:
				put_submit_cmd = 'qsub ' + self.put_data_script_name

			completed_submit_process = subprocess.run(
				put_submit_cmd, shell=True, check=True, stdout=subprocess.PIPE, universal_newlines=True)
			put_job_no = str_utils.remove_ending_new_lines(completed_submit_process.stdout)
			return put_job_no, [put_job_no]

		else:
			module_logger.info("Put data job not submitted")
			return None, None

	def submit_check_jobs(self, stage, prior_job=None):
		module_logger.debug(debug_utils.get_name())

		if stage >= ccf_processing_stage.ProcessingStage.CHECK_DATA:
			if prior_job:
				check_submit_cmd = 'qsub -W depend=afterok:' + prior_job + ' ' + self.check_data_job_script_name
			else:
				check_submit_cmd = 'qsub ' + self.check_data_job_script_name

			completed_submit_process = subprocess.run(
				check_submit_cmd, shell=True, check=True, stdout=subprocess.PIPE, universal_newlines=True)
			check_job_no = str_utils.remove_ending_new_lines(completed_submit_process.stdout)
			return check_job_no, [check_job_no]

		else:
			module_logger.info("Check data job not submitted")
			return None, None

	def submit_no_longer_running_jobs(self, stage, prior_job=None):
		module_logger.debug(debug_utils.get_name())

		if prior_job:
			cmd = 'qsub -W depend=afterany:' + prior_job + ' ' + self.mark_no_longer_running_script_name
		else:
			cmd = 'qsub ' + self.mark_no_longer_running_script_name

		completed_submit_process = subprocess.run(
			cmd, shell=True, check=True, stdout=subprocess.PIPE, universal_newlines=True)
		job_no = str_utils.remove_ending_new_lines(completed_submit_process.stdout)
		return job_no, [job_no]
		
	@abc.abstractmethod
	def create_process_data_job_script(self):
		raise NotImplementedError()

	def create_scripts(self, stage):
		module_logger.debug(debug_utils.get_name())

		if stage >= ccf_processing_stage.ProcessingStage.PREPARE_SCRIPTS:
			self.create_get_data_job_script()
			self.create_process_data_job_script()
			self.create_clean_data_script()
			self.create_put_data_script()
			self.create_check_data_job_script()
			self.create_mark_no_longer_running_script()
			
		else:
			module_logger.info("Scripts not created")

	def do_job_submissions(self, processing_stage):
		submitted_jobs_list = []
		prior = None

		# create scripts
		self.create_scripts(stage=processing_stage)
		
		# create running status marker file to indicate that jobs are queued
		self.mark_running_status(stage=processing_stage)
			
		# Submit job(s) to get the data
		last_get_data_job_no, all_get_data_job_nos = self.submit_get_data_jobs(stage=processing_stage, prior_job=prior)
		if all_get_data_job_nos:
			submitted_jobs_list.append((ccf_processing_stage.ProcessingStage.GET_DATA.name, all_get_data_job_nos))
		if last_get_data_job_no:
			prior = last_get_data_job_no

		# Submit job(s) to process the data
		last_process_job_no, all_process_data_job_nos = self.submit_process_data_jobs(stage=processing_stage, prior_job=prior)
		if all_process_data_job_nos:
			submitted_jobs_list.append((ccf_processing_stage.ProcessingStage.PROCESS_DATA.name, all_process_data_job_nos))
		if last_process_job_no:
			prior = last_process_job_no

		# Submit job(s) to clean the data
		last_clean_job_no, all_clean_data_job_nos = self.submit_clean_data_jobs(stage=processing_stage, prior_job=prior)
		if all_process_data_job_nos:
			submitted_jobs_list.append((ccf_processing_stage.ProcessingStage.CLEAN_DATA.name, all_clean_data_job_nos))
		if last_clean_job_no:
			prior = last_clean_job_no

		# Submit job(s) to put the resulting data in the DB
		last_put_job_no, all_put_job_nos = self.submit_put_data_jobs(stage=processing_stage, prior_job=prior)
		if all_put_job_nos:
			submitted_jobs_list.append((ccf_processing_stage.ProcessingStage.PUT_DATA.name, all_put_job_nos))
		if last_put_job_no:
			prior = last_put_job_no

		# Submit job(s) to perform completeness check
		last_check_job_no, all_check_job_nos = self.submit_check_jobs(stage=processing_stage, prior_job=prior)
		if all_check_job_nos:
			submitted_jobs_list.append((ccf_processing_stage.ProcessingStage.CHECK_DATA.name, all_check_job_nos))
		if last_check_job_no:
			prior = last_check_job_no

		# Submit job(s) to change running status marker file
		last_running_status_job_no, all_running_status_job_nos = self.submit_no_longer_running_jobs(stage=processing_stage, prior_job=prior)
		if all_running_status_job_nos:
			submitted_jobs_list.append(('Complete Running Status', all_running_status_job_nos))
		if last_running_status_job_no:
			prior = last_running_status_job_no
			
		return submitted_jobs_list

	def submit_jobs(self, processing_stage=ccf_processing_stage.ProcessingStage.CHECK_DATA):
		module_logger.debug(debug_utils.get_name() + ": processing_stage: " + str(processing_stage))

		module_logger.info("-----")

		module_logger.info("Submitting " + self.PIPELINE_NAME + " jobs for")
		module_logger.info("  Project: " + self.project)
		module_logger.info("  Subject: " + self.subject)
		module_logger.info("  Session: " + self.session)
		module_logger.info("	Stage: " + str(processing_stage))

		# make sure working directories do not have the same name based on
		# the same start time by sleeping a few seconds
		time.sleep(5)

		# build the working directory name
		os.makedirs(name=self.working_directory_name)
		os.makedirs(name=self.check_data_directory_name)
		os.makedirs(name=self.mark_completion_directory_name)
		
		module_logger.info("Output Resource Name: " + self.output_resource_name)

		# clean output resource if requested
		if self.clean_output_resource_first:
			module_logger.info("Deleting resource: " + self.output_resource_name + " for:")
			module_logger.info("  project: " + self.project)
			module_logger.info("  subject: " + self.subject)
			module_logger.info("  session: " + self.session)

			delete_resource.delete_resource(
				self.username, self.password,
				str_utils.get_server_name(self.server),
				self.project, self.subject, self.session,
				self.output_resource_name)

		return self.do_job_submissions(processing_stage)
