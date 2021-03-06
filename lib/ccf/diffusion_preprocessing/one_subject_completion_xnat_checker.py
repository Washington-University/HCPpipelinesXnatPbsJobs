#!/usr/bin/env python3

# import of built-in modules
import os
import sys

# import of third-party modules

# import of local modules
import ccf.archive as ccf_archive
import ccf.diffusion_preprocessing.one_subject_job_submitter as one_subject_job_submitter
import ccf.one_subject_completion_xnat_checker as one_subject_completion_xnat_checker
import ccf.subject as ccf_subject
import utils.my_argparse as my_argparse
import utils.file_utils as file_utils
import utils.os_utils as os_utils

class OneSubjectCompletionXnatChecker(one_subject_completion_xnat_checker.OneSubjectCompletionXnatChecker):

	def __init__(self):
		super().__init__()
		
	@property
	def processing_name(self):
		return 'DiffusionPreprocessing'	

	@property
	def PIPELINE_NAME(self):
		return one_subject_job_submitter.OneSubjectJobSubmitter.MY_PIPELINE_NAME()

	def my_resource(self, archive, subject_info):
		return archive.diffusion_preproc_dir_full_path(subject_info)

	def my_prerequisite_dir_full_paths(self, archive, subject_info):
		dirs = []
		dirs.append(archive.structural_preproc_dir_full_path(subject_info))
		return dirs


	def list_of_expected_files(self, working_dir, fieldmap, subject_info):

		ptFilePath = os.sep + 'pipeline_tools' + os.sep + 'pipelines' + os.sep + 'expected_files' + os.sep + 'DiffusionPreprocessing.txt'
		print(ptFilePath)
		hcp_run_utils = os_utils.getenv_required('HCP_RUN_UTILS')
		if os.path.isfile(ptFilePath):
			f = open(ptFilePath)
		elif os.path.isfile(hcp_run_utils + os.sep + self.processing_name + os.sep
				 + self.expected_output_files_template_filename(fieldmap)):
			f = open(hcp_run_utils + os.sep + self.processing_name + os.sep
					 + self.expected_output_files_template_filename(fieldmap))
		else:
			xnat_pbs_jobs = os_utils.getenv_required('XNAT_PBS_JOBS')
			f = open(xnat_pbs_jobs + os.sep + self.processing_name + os.sep
					 + self.expected_output_files_template_filename(fieldmap))
			
		root_dir = os.sep.join([working_dir, subject_info.subject_id + '_' + subject_info.classifier])
		l = file_utils.build_filename_list_from_file(f, root_dir,
			 subjectid=subject_info.subject_id + '_' + subject_info.classifier,
			 scan=subject_info.extra)
		return l

	
if __name__ == "__main__":

	parser = my_argparse.MyArgumentParser(
		description="Program to check for completion of Diffusion Preprocessing.")

	# mandatory arguments
	parser.add_argument('-p', '--project', dest='project', required=True, type=str)
	parser.add_argument('-s', '--subject', dest='subject', required=True, type=str)
	parser.add_argument('-c', '--classifier', dest='classifier', required=True, type=str)
	parser.add_argument('-f', '--fieldmap', dest='fieldmap', required=False, type=str ,default='NONE')

	# optional arguments
	parser.add_argument('-v', '--verbose', dest='verbose', action='store_true',
						required=False, default=False)
	parser.add_argument('-o', '--output', dest='output', required=False, type=str)
	parser.add_argument('-a', '--check-all', dest='check_all', action='store_true',
						required=False, default=False)

	# parse the command line arguments
	args = parser.parse_args()

	# check the specified subject for diffusion preprocessing completion
	archive = ccf_archive.CcfArchive()
	subject_info = ccf_subject.SubjectInfo(
		project=args.project,
		subject_id=args.subject,
		classifier=args.classifier)
	completion_checker = OneSubjectCompletionXnatChecker()

	if args.output:
		processing_output = open(args.output, 'w')
	else:
		processing_output = sys.stdout

	if completion_checker.is_processing_complete(
			archive=archive,
			fieldmap=args.fieldmap,
			subject_info=subject_info,
			verbose=args.verbose,
			output=processing_output,
			short_circuit=not args.check_all):
		print("Exiting with 0 code - Completion Check Successful")
		exit(0)
	else:
		print("Existing wih 1 code - Completion Check Unsuccessful")
		exit(1)
