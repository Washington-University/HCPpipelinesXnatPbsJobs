#!/usr/bin/env python3

# import of built-in modules
import contextlib
import glob
import logging
import os
import shutil
import stat
import subprocess
import sys
import random
# import of third-party modules

# import of local modules
import ccf.one_subject_job_submitter as one_subject_job_submitter
import ccf.processing_stage as ccf_processing_stage
import ccf.subject as ccf_subject
import utils.debug_utils as debug_utils
import utils.os_utils as os_utils
import utils.str_utils as str_utils
import utils.user_utils as user_utils
import ccf.archive as ccf_archive

# authorship information
__author__ = "Timothy B. Brown"
__copyright__ = "Copyright 2020, Connectome Coordination Facility"
__maintainer__ = "Junil Chang"

# create a module logger
module_logger = logging.getLogger(__name__)
# Note: This can be overidden by log file configuration
module_logger.setLevel(logging.WARNING)


class OneSubjectJobSubmitter(one_subject_job_submitter.OneSubjectJobSubmitter):

	_SEVEN_MM_TEMPLATE_PROJECTS = os_utils.getenv_required('SEVEN_MM_TEMPLATE_PROJECTS')
	_CONNECTOME_SKYRA_SCANNER_PROJECTS = os_utils.getenv_required('CONNECTOME_SKYRA_SCANNER_PROJECTS')
	_PRISMA_3T_PROJECTS = os_utils.getenv_required('PRISMA_3T_PROJECTS')
	_SCRATCH_PROCESSING_DIR = os_utils.getenv_required('SCRATCH_PROCESSING_DIR')
	_SUPPRESS_FREESURFER_ASSESSOR_JOB = True
	
	@classmethod
	def MY_PIPELINE_NAME(cls):
		return 'StructuralPreprocessing'

	def __init__(self, archive, build_home):
		super().__init__(archive, build_home)
	
	@property
	def PIPELINE_NAME(self):
		return OneSubjectJobSubmitter.MY_PIPELINE_NAME()

	@property
	def WORK_NODE_COUNT(self):
		return 1

	@property
	def WORK_PPN(self):
		return 1

	# @property
	# def FIELDMAP_TYPE_SPEC(self):
	#	 return "SE"  # Spin Echo Field Maps

	# @property
	# def PHASE_ENCODING_DIR_SPEC(self):
	#   return "PA" # Posterior-to-Anterior and Anterior to Posterior

	@property
	def use_prescan_normalized(self):
		return self._use_prescan_normalized

	@use_prescan_normalized.setter
	def use_prescan_normalized(self, value):
		self._use_prescan_normalized = value
		module_logger.debug(debug_utils.get_name() + ": set to " + str(self._use_prescan_normalized))
	
	@property
	def brain_size(self):
		return self._brain_size

	@brain_size.setter
	def brain_size(self, value):
		self._brain_size = value
		module_logger.debug(debug_utils.get_name() + ": set to " +
							str(self._brain_size))

	def _template_size_str(self):
		if self.project == None:
			raise ValueError("project attribute must be set before template size can be determined")

		if self.project in OneSubjectJobSubmitter._SEVEN_MM_TEMPLATE_PROJECTS:
			size_str = "0.7mm"
		else:
			size_str = "0.8mm"

		return size_str
	
	@property
	def T1W_TEMPLATE_NAME(self):
		return "MNI152_T1_" + self._template_size_str() + ".nii.gz"

	@property
	def T1W_TEMPLATE_BRAIN_NAME(self):
		return "MNI152_T1_" + self._template_size_str() + "_brain.nii.gz"

	@property
	def T1W_TEMPLATE_2MM_NAME(self):
		return "MNI152_T1_2mm.nii.gz"

	@property
	def T2W_TEMPLATE_NAME(self):
		return "MNI152_T2_" + self._template_size_str() + ".nii.gz"

	@property
	def T2W_TEMPLATE_BRAIN_NAME(self):
		return "MNI152_T2_" + self._template_size_str() + "_brain.nii.gz"

	@property
	def T2W_TEMPLATE_2MM_NAME(self):
		return "MNI152_T2_2mm.nii.gz"

	@property
	def TEMPLATE_MASK_NAME(self):
		return "MNI152_T1_" + self._template_size_str() + "_brain_mask.nii.gz"

	@property
	def TEMPLATE_2MM_MASK_NAME(self):
		return "MNI152_T1_2mm_brain_mask_dil.nii.gz"

	@property
	def FNIRT_CONFIG_FILE_NAME(self):
		return "T1_2_MNI152_2mm.cnf"

	@property
	def CONNECTOME_GDCOEFFS_FILE_NAME(self):
		return "coeff_SC72C_Skyra.grad"
	
	@property
	def PRISMA_3T_GDCOEFFS_FILE_NAME(self):
		return "Prisma_3T_coeff_AS82.grad"

	@property
	def TOPUP_CONFIG_FILE_NAME(self):
		return "b02b0.cnf"

	@property
	def freesurfer_assessor_script_name(self):
		module_logger.debug(debug_utils.get_name())
		return self.scripts_start_name + '.XNAT_CREATE_FREESURFER_ASSESSOR_job.sh'

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
		script.write('module load ' + self._get_xnat_pbs_setup_script_singularity_version() + os.linesep)
		script.write(os.linesep)
		script.write('singularity exec -B ' + self._get_xnat_pbs_setup_script_archive_root() + ',' + self._get_xnat_pbs_setup_script_singularity_bind_path() + ' ' + self._get_xnat_pbs_setup_script_singularity_container_xnat_path() + ' ' + self.get_data_program_path  + ' \\' + os.linesep)
		script.write('  --project=' + self.project + ' \\' + os.linesep)
		script.write('  --subject=' + self.subject + ' \\' + os.linesep)
		script.write('  --classifier=' + self.classifier + ' \\' + os.linesep)
		if self.scan:
			script.write('  --scan=' + self.scan + ' \\' + os.linesep)
		script.write('  --working-dir=' + self.working_directory_name + ' \\' + os.linesep)
		if self.use_prescan_normalized:
			script.write('  --use-prescan-normalized' + ' \\' + os.linesep)
		script.write('  --delay-seconds=120' + os.linesep)
		script.write(os.linesep)
		script.write('rm -rf ' + self.working_directory_name + os.sep + self.subject + '_' + self.classifier + '/unprocessed/T1w_MPR_vNav_4e_RMS' + os.linesep)
		script.close()
		os.chmod(script_name, stat.S_IRWXU | stat.S_IRWXG)


	def _get_first_t1w_resource_fullpath(self, subject_info):
		t1w_resource_paths = self.archive.available_t1w_unproc_dir_full_paths(subject_info)
		if len(t1w_resource_paths) > 0:
			return t1w_resource_paths[0]
		else:
			raise RuntimeError("Session has no T1w resources")
		
	def _has_spin_echo_field_maps(self, subject_info):
		first_t1w_resource_path = self._get_first_t1w_resource_fullpath(subject_info)
		path_expr = first_t1w_resource_path + os.sep + '*SpinEchoFieldMap*' + '.nii.gz'
		spin_echo_file_list = glob.glob(path_expr)
		return len(spin_echo_file_list) > 0

	def _has_siemens_gradient_echo_field_maps(self, subject_info):
		first_t1w_resource_path = self._get_first_t1w_resource_fullpath(subject_info)
		path_expr_Magnitude = first_t1w_resource_path + os.sep + '*FieldMap_Magnitude*' + '.nii.gz'
		path_expr_Phase = first_t1w_resource_path + os.sep + '*FieldMap_Phase*' + '.nii.gz'
		siemens_gradient_echo_file_list = glob.glob(path_expr_Magnitude) + glob.glob(path_expr_Phase)
		return len(siemens_gradient_echo_file_list) > 1	
	
	def _get_fmap_phase_file_path(self, subject_info):
		first_t1w_resource_path = self._get_first_t1w_resource_fullpath(subject_info)
		path_expr = first_t1w_resource_path + os.sep + '*FieldMap_Phase*' + '.nii.gz'
		fmap_phase_list = glob.glob(path_expr)
		
		if len(fmap_phase_list) > 0:
			fmap_phase_file = fmap_phase_list[0]
		else:
			raise RuntimeError("First T1w has no Phase FieldMap: " + path_expr)

		return fmap_phase_file

	def _get_fmap_phase_file_name(self, subject_info):
		full_path = self._get_fmap_phase_file_path(subject_info)
		basename = os.path.basename(full_path)
		return basename
	
	def _get_fmap_mag_file_path(self, subject_info):
		first_t1w_resource_path = self._get_first_t1w_resource_fullpath(subject_info)
		path_expr = first_t1w_resource_path + os.sep + '*FieldMap_Magnitude*' + '.nii.gz'
		fmap_mag_list = glob.glob(path_expr)

		if len(fmap_mag_list) > 0:
			fmap_mag_file = fmap_mag_list[0]
		else:
			raise RuntimeError("First T1w has no Magnitude FieldMap: " + path_expr)

		return fmap_mag_file
		
	def _get_fmap_mag_file_name(self, subject_info):
		full_path = self._get_fmap_mag_file_path(subject_info)
		basename = os.path.basename(full_path)
		return basename

	def _get_positive_spin_echo_path(self, subject_info):
		first_t1w_resource_path = self._get_first_t1w_resource_fullpath(subject_info)
		path_expr = first_t1w_resource_path + os.sep + '*SpinEchoFieldMap*' + self.PAAP_POSITIVE_DIR + '.nii.gz'
		positive_spin_echo_file_list = glob.glob(path_expr)

		if len(positive_spin_echo_file_list) > 0:
			positive_spin_echo_file = positive_spin_echo_file_list[0]
		else:
			raise RuntimeError("First T1w resource/scan has no positive spin echo field map")

		return positive_spin_echo_file

	def _get_positive_spin_echo_file_name(self, subject_info):
		full_path = self._get_positive_spin_echo_path(subject_info)
		basename = os.path.basename(full_path)
		return basename

	def _get_negative_spin_echo_path(self, subject_info):
		first_t1w_resource_path = self._get_first_t1w_resource_fullpath(subject_info)
		path_expr = first_t1w_resource_path + os.sep + '*SpinEchoFieldMap*' + self.PAAP_NEGATIVE_DIR + '.nii.gz'
		negative_spin_echo_file_list = glob.glob(path_expr)

		if len(negative_spin_echo_file_list) > 0:
			negative_spin_echo_file = negative_spin_echo_file_list[0]
		else:
			raise RuntimeError("First T1w resource/scan has no negative spin echo field map")

		return negative_spin_echo_file

	def _get_negative_spin_echo_file_name(self, subject_info):
		full_path = self._get_negative_spin_echo_path(subject_info)
		basename = os.path.basename(full_path)
		return basename

	def _get_first_t1w_name(self, subject_info):
		t1w_unproc_names = self.archive.available_t1w_unproc_names(subject_info)
		if len(t1w_unproc_names) > 0:
			first_t1w_name = t1w_unproc_names[0]
		else:
			raise RuntimeError("Session has no available T1w scans")

		return first_t1w_name

	def _get_first_t1w_norm_name(self, subject_info):
		non_norm_name = self._get_first_t1w_name(subject_info)
		vNav_loc = non_norm_name.find('vNav')
		norm_name = non_norm_name[:vNav_loc] + 'vNav' + '_Norm' + non_norm_name[vNav_loc+4:]
		return norm_name
	
	def _get_first_t1w_directory_name(self, subject_info):
		first_t1w_name = self._get_first_t1w_name(subject_info)
		return first_t1w_name
	
	def _get_first_t1w_resource_name(self, subject_info):
		return self._get_first_t1w_name(subject_info) + self.archive.NAME_DELIMITER + self.archive.UNPROC_SUFFIX
	
	def _get_first_t1w_file_name(self, subject_info):
		if self.use_prescan_normalized:
			return self.session + self.archive.NAME_DELIMITER + self._get_first_t1w_norm_name(subject_info) + '.nii.gz'
		else:
			return self.session + self.archive.NAME_DELIMITER + self._get_first_t1w_name(subject_info) + '.nii.gz'

	def _get_first_t2w_name(self, subject_info):
		t2w_unproc_names = self.archive.available_t2w_unproc_names(subject_info)
		if len(t2w_unproc_names) > 0:
			first_t2w_name = t2w_unproc_names[0]
		else:
			raise RuntimeError("Session has no available T2w scans")
		
		return first_t2w_name

	def _get_first_t2w_norm_name(self, subject_info):
		non_norm_name = self._get_first_t2w_name(subject_info)
		vNav_loc = non_norm_name.find('vNav')
		norm_name = non_norm_name[:vNav_loc] + 'vNav' + '_Norm' + non_norm_name[vNav_loc+4:]
		return norm_name
	
	def _get_first_t2w_directory_name(self, subject_info):
		first_t2w_name = self._get_first_t2w_name(subject_info)
		return first_t2w_name
	
	def _get_first_t2w_resource_name(self, subject_info):
		return self._get_first_t2w_name(subject_info) + self.archive.NAME_DELIMITER + self.archive.UNPROC_SUFFIX

	def _get_first_t2w_file_name(self, subject_info):
		if self.use_prescan_normalized:
			return self.session + self.archive.NAME_DELIMITER + self._get_first_t2w_norm_name(subject_info) + '.nii.gz'
		else:
			return self.session + self.archive.NAME_DELIMITER + self._get_first_t2w_name(subject_info) + '.nii.gz'

	def create_process_data_job_script(self):

		project_build_dir = self.build_home + os.sep + self.project
		pipeline_processing_dir = self.working_directory_name.replace(project_build_dir + os.sep, '');
		scratch_processing_dir = self._SCRATCH_PROCESSING_DIR + os.sep + self.project
		if not os.path.exists(scratch_processing_dir):
			os.mkdir(scratch_processing_dir)

		module_logger.debug(debug_utils.get_name())

		xnat_pbs_jobs_control_folder = os_utils.getenv_required('XNAT_PBS_JOBS_CONTROL')

		subject_info = ccf_subject.SubjectInfo(self.project, self.subject, self.classifier)

		script_name = self.process_data_job_script_name

		with contextlib.suppress(FileNotFoundError):
			os.remove(script_name)

		walltime_limit_str = str(self.walltime_limit_hours) + ':00:00'
		vmem_limit_str = str(self.vmem_limit_gbs) + 'gb'

		resources_line = '#PBS -l nodes=' + str(self.WORK_NODE_COUNT)
		resources_line += ':ppn=' + str(self.WORK_PPN) + ':haswell'
		resources_line += ',walltime=' + walltime_limit_str
		resources_line += ',mem=' + vmem_limit_str
		stdout_line = '#PBS -o ' + self.working_directory_name
		stderr_line = '#PBS -e ' + self.working_directory_name
		xnat_pbs_setup_singularity_load = 'module load ' + self._get_xnat_pbs_setup_script_singularity_version()
		xnat_pbs_setup_singularity_process = 'singularity exec -B ' \
											+ self._get_xnat_pbs_setup_script_archive_root() + ',' + self._get_xnat_pbs_setup_script_singularity_bind_path() \
											+ ',' + self._get_xnat_pbs_setup_script_gradient_coefficient_path() + ':/export/HCP/gradient_coefficient_files' \
											+ ' ' + self._get_xnat_pbs_setup_script_singularity_container_path() + ' ' + self._get_xnat_pbs_setup_script_singularity_qunexrun_path()
		parameter_line   = '  --parameterfolder=' + self._get_xnat_pbs_setup_script_singularity_qunexparameter_path()
		#studyfolder_line   = '  --studyfolder=' + self.working_directory_name + '/' + self.subject + '_' + self.classifier
		studyfolder_line   = '  --studyfolder=' + scratch_processing_dir + os.sep + pipeline_processing_dir + os.sep + self.subject + '_' + self.classifier
		subject_line   = '  --subjects=' + self.subject+ '_' + self.classifier
		overwrite_line = '  --overwrite=yes'
		hcppipelineprocess_line = '  --hcppipelineprocess=StructuralPreprocessing'
		with open(script_name, 'w') as script:
			script.write(resources_line + os.linesep)
			script.write(stdout_line + os.linesep)
			script.write(stderr_line + os.linesep)
			script.write(os.linesep)
			script.write(xnat_pbs_setup_singularity_load + os.linesep)
			script.write(os.linesep)
			script.write('# TEMPORARILY MOVE PROCESSING DIRECTORY TO SCRATCH SPACE DUE TO "Cannot allocate memory" ERRORS IN BUILD SPACE' + os.linesep)
			script.write('mv ' + self.working_directory_name + " " + scratch_processing_dir + os.linesep)
			script.write(os.linesep)
			script.write(xnat_pbs_setup_singularity_process+ ' \\' + os.linesep)
			script.write(parameter_line + ' \\' + os.linesep)
			script.write(studyfolder_line + ' \\' + os.linesep)
			script.write(subject_line + ' \\' + os.linesep)
			script.write(overwrite_line + ' \\' + os.linesep)
			script.write(hcppipelineprocess_line + os.linesep)
			script.write(os.linesep)
			script.write('# MOVE PROCESSING BACK' + os.linesep)
			script.write('mv ' + scratch_processing_dir + os.sep + pipeline_processing_dir + ' ' + project_build_dir + os.linesep)
			script.write(os.linesep)
			os.chmod(script_name, stat.S_IRWXU | stat.S_IRWXG)

	def create_freesurfer_assessor_script(self):
		module_logger.debug(debug_utils.get_name())

		# copy the .XNAT_CREATE_FREESURFER_ASSESSOR script to the working directory
		freesurfer_assessor_source_path = self.xnat_pbs_jobs_home
		freesurfer_assessor_source_path += os.sep + self.PIPELINE_NAME
		freesurfer_assessor_source_path += os.sep + self.PIPELINE_NAME
		freesurfer_assessor_source_path += '.XNAT_CREATE_FREESURFER_ASSESSOR'

		freesurfer_assessor_dest_path = self.working_directory_name
		freesurfer_assessor_dest_path += os.sep + self.PIPELINE_NAME
		freesurfer_assessor_dest_path += '.XNAT_CREATE_FREESURFER_ASSESSOR'

		shutil.copy(freesurfer_assessor_source_path, freesurfer_assessor_dest_path)
		os.chmod(freesurfer_assessor_dest_path, stat.S_IRWXU | stat.S_IRWXG)

		# write the freesurfer assessor submission script (that calls the .XNAT_CREATE_FREESURFER_ASSESSOR script)

		script_name = self.freesurfer_assessor_script_name

		with contextlib.suppress(FileNotFoundError):
			os.remove(script_name)

		script = open(script_name, 'w')

		self._write_bash_header(script)
		script.write('#PBS -l nodes=1:ppn=1,walltime=4:00:00,mem=4gb' + os.linesep)
		script.write('#PBS -o ' + self.working_directory_name + os.linesep)
		script.write('#PBS -e ' + self.working_directory_name + os.linesep)
		script.write(os.linesep)
		script.write('source ' + self._get_xnat_pbs_setup_script_path() + ' ' + self._get_db_name() + os.linesep)
		script.write(os.linesep)
		script_line	= freesurfer_assessor_dest_path
		user_line	  = '  --user='		+ self.username
		password_line  = '  --password='	+ self.password
		server_line	= '  --server='	  + str_utils.get_server_name(self.server)
		project_line   = '  --project='	 + self.project
		subject_line   = '  --subject='	 + self.subject
		session_line   = '  --session='	 + self.session
		session_classifier_line = '  --session-classifier=' + self.classifier
		wdir_line	  = '  --working-dir=' + self.working_directory_name

		script.write(script_line   + ' \\' + os.linesep)
		script.write(user_line	 + ' \\' + os.linesep)
		script.write(password_line + ' \\' + os.linesep)
		script.write(server_line + ' \\' + os.linesep)
		script.write(project_line + ' \\' + os.linesep)
		script.write(subject_line + ' \\' + os.linesep)
		script.write(session_line + ' \\' + os.linesep)
		script.write(session_classifier_line + ' \\' + os.linesep)
		script.write(wdir_line + os.linesep)

		script.close()
		os.chmod(script_name, stat.S_IRWXU | stat.S_IRWXG)

	def create_scripts(self, stage):
		module_logger.debug(debug_utils.get_name())
		super().create_scripts(stage)

		if OneSubjectJobSubmitter._SUPPRESS_FREESURFER_ASSESSOR_JOB:
			return

		if stage >= ccf_processing_stage.ProcessingStage.PREPARE_SCRIPTS:
			self.create_freesurfer_assessor_script()

	def submit_process_data_jobs(self, stage, prior_job=None):
		module_logger.debug(debug_utils.get_name())

		# go ahead and submit the standard process data job and then
		# submit an additional freesurfer assessor job

		standard_process_data_jobno, all_process_data_jobs = super().submit_process_data_jobs(stage, prior_job)

		if OneSubjectJobSubmitter._SUPPRESS_FREESURFER_ASSESSOR_JOB:
			module_logger.info("freesufer assessor job not submitted because freesurfer assessor creation has been suppressed")
			return standard_process_data_jobno, all_process_data_jobs
		
		if stage >= ccf_processing_stage.ProcessingStage.PROCESS_DATA:
			if standard_process_data_jobno:
				fs_submit_cmd = 'qsub -W depend=afterok:' + standard_process_data_jobno + ' ' + self.freesurfer_assessor_script_name
			else:
				fs_submit_cmd = 'qsub ' + self.freesurfer_assessor_script_name

			completed_submit_process = subprocess.run(
				fs_submit_cmd, shell=True, check=True, stdout=subprocess.PIPE, universal_newlines=True)
			fs_job_no = str_utils.remove_ending_new_lines(completed_submit_process.stdout)
			all_process_data_jobs.append(fs_job_no)
			return fs_job_no, all_process_data_jobs

		else:
			module_logger.info("freesurfer assessor job not submitted because of requested processing stage")
			return standard_process_data_jobno, all_process_data_jobs
			
	def mark_running_status(self, stage):
		module_logger.debug(debug_utils.get_name())

		if stage > ccf_processing_stage.ProcessingStage.PREPARE_SCRIPTS:
			mark_cmd = self._xnat_pbs_jobs_home
			mark_cmd += os.sep + self.PIPELINE_NAME 
			mark_cmd += os.sep + self.PIPELINE_NAME
			mark_cmd += '.XNAT_MARK_RUNNING_STATUS' 
			mark_cmd += ' --user=' + self.username
			mark_cmd += ' --password=' + self.password
			mark_cmd += ' --server=' + str_utils.get_server_name(self.put_server)
			mark_cmd += ' --project=' + self.project
			mark_cmd += ' --subject=' + self.subject
			mark_cmd += ' --classifier=' + self.classifier
			mark_cmd += ' --resource=RunningStatus'
			mark_cmd += ' --queued'

			completed_mark_cmd_process = subprocess.run(
				mark_cmd, shell=True, check=True, stdout=subprocess.PIPE, universal_newlines=True)
			print(completed_mark_cmd_process.stdout)
			
			return

if __name__ == "__main__":
	import ccf.structural_preprocessing.one_subject_run_status_checker as one_subject_run_status_checker

	xnat_server = os_utils.getenv_required('XNAT_PBS_JOBS_XNAT_SERVER')
	username, password = user_utils.get_credentials(xnat_server)
	archive = ccf_archive.CcfArchive()	
	
	subject = ccf_subject.SubjectInfo(sys.argv[1], sys.argv[2], sys.argv[3])
	submitter = OneSubjectJobSubmitter(archive, archive.build_home)
	
	run_status_checker = one_subject_run_status_checker.OneSubjectRunStatusChecker()
	if run_status_checker.get_queued_or_running(subject):
		print("-----")
		print("NOT SUBMITTING JOBS FOR")
		print("project: " + subject.project)
		print("subject: " + subject.subject_id)
		print("session classifier: " + subject.classifier)
		print("JOBS ARE ALREADY QUEUED OR RUNNING")
		print ('Process terminated')
		sys.exit()	
		
	job_submitter=OneSubjectJobSubmitter(archive, archive.build_home)	
	put_server_name = os.environ.get("XNAT_PBS_JOBS_PUT_SERVER_LIST").split(" ")
	put_server = random.choice(put_server_name)

	clean_output_first = eval(sys.argv[4])
	processing_stage_str = sys.argv[5]
	processing_stage = submitter.processing_stage_from_string(processing_stage_str)
	walltime_limit_hrs = sys.argv[6]
	vmem_limit_gbs = sys.argv[7]
	output_resource_suffix = sys.argv[8]
	brain_size = sys.argv[9]
	use_prescan_normalized = eval(sys.argv[10])	
	
	print("-----")
	print("\tSubmitting", submitter.PIPELINE_NAME, "jobs for:")
	print("\t			   project:", subject.project)
	print("\t			   subject:", subject.subject_id)
	print("\t	session classifier:", subject.classifier)
	print("\t			put_server:", put_server)
	print("\t	clean_output_first:", clean_output_first)
	print("\t	  processing_stage:", processing_stage)
	print("\t	walltime_limit_hrs:", walltime_limit_hrs)
	print("\t		mem_limit_gbs:", vmem_limit_gbs)
	print("\toutput_resource_suffix:", output_resource_suffix)
	print("\t			brain_size:", brain_size)
	print("\tuse_prescan_normalized:", use_prescan_normalized)
	
	# configure one subject submitter
			
	# user and server information
	submitter.username = username
	submitter.password = password
	submitter.server = 'http://' + os_utils.getenv_required('XNAT_PBS_JOBS_XNAT_SERVER')

	# subject and project information
	submitter.project = subject.project
	submitter.subject = subject.subject_id
	submitter.session = subject.subject_id + '_' + subject.classifier
	submitter.classifier = subject.classifier
	submitter.brain_size = brain_size
	submitter.use_prescan_normalized = use_prescan_normalized
			
	# job parameters
	submitter.clean_output_resource_first = clean_output_first
	submitter.put_server = put_server
	submitter.walltime_limit_hours = walltime_limit_hrs
	submitter.vmem_limit_gbs = vmem_limit_gbs
	submitter.output_resource_suffix = output_resource_suffix

	# submit jobs
	submitted_job_list = submitter.submit_jobs(processing_stage)
	print("\tsubmitted jobs:", submitted_job_list)
	print("-----")
