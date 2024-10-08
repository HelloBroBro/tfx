# Copyright 2019 Google LLC. All Rights Reserved.
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
"""E2E Beam tests for CLI."""

import codecs
import locale
import os

from click import testing as click_testing

from tfx.dsl.io import fileio
from tfx.tools.cli.cli_main import cli_group
from tfx.utils import io_utils
from tfx.utils import test_case_utils

import pytest


@pytest.mark.e2e
class CliBeamEndToEndTest(test_case_utils.TfxTest):

  def setUp(self):
    super().setUp()

    # Change the encoding for Click since Python 3 is configured to use ASCII as
    # encoding for the environment.
    if codecs.lookup(locale.getpreferredencoding()).name == 'ascii':
      os.environ['LANG'] = 'en_US.utf-8'

    # Setup beam_home in a temp directory
    self._home = self.tmp_dir
    self._beam_home = os.path.join(self._home, 'beam')
    self.enter_context(
        test_case_utils.override_env_var('BEAM_HOME', self._beam_home))
    self.enter_context(
        test_case_utils.override_env_var('HOME', self._home))

    # Testdata path.
    self._testdata_dir = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 'testdata')

    # Copy data.
    chicago_taxi_pipeline_dir = os.path.join(
        os.path.dirname(
            os.path.dirname(
                os.path.dirname(os.path.dirname(os.path.abspath(__file__))))),
        'examples', 'chicago_taxi_pipeline', '')
    data_dir = os.path.join(chicago_taxi_pipeline_dir, 'data', 'simple')
    content = fileio.listdir(data_dir)
    assert content, 'content in {} is empty'.format(data_dir)
    target_data_dir = os.path.join(self._home, 'taxi', 'data', 'simple')
    io_utils.copy_dir(data_dir, target_data_dir)
    assert fileio.isdir(target_data_dir)
    content = fileio.listdir(target_data_dir)
    assert content, 'content in {} is {}'.format(target_data_dir, content)
    io_utils.copy_file(
        os.path.join(chicago_taxi_pipeline_dir, 'taxi_utils.py'),
        os.path.join(self._home, 'taxi', 'taxi_utils.py'))

    # Initialize CLI runner.
    self.runner = click_testing.CliRunner()

  def _valid_create_and_check(self, pipeline_path, pipeline_name):
    handler_pipeline_path = os.path.join(self._beam_home, pipeline_name)

    # Create a pipeline.
    result = self.runner.invoke(cli_group, [
        'pipeline', 'create', '--engine', 'beam', '--pipeline_path',
        pipeline_path
    ])
    self.assertIn('CLI', result.output)
    self.assertIn('Creating pipeline', result.output)
    self.assertTrue(
        fileio.exists(
            os.path.join(handler_pipeline_path, 'pipeline_args.json')))
    self.assertIn('Pipeline "{}" created successfully.'.format(pipeline_name),
                  result.output)

  def testPipelineCreate(self):
    # Create a pipeline.
    pipeline_path = os.path.join(self._testdata_dir, 'test_pipeline_beam_1.py')
    pipeline_name = 'chicago_taxi_beam'
    self._valid_create_and_check(pipeline_path, pipeline_name)

    # Test pipeline create when pipeline already exists.
    result = self.runner.invoke(cli_group, [
        'pipeline', 'create', '--engine', 'beam', '--pipeline_path',
        pipeline_path
    ])
    self.assertIn('CLI', result.output)
    self.assertIn('Creating pipeline', result.output)
    self.assertTrue('Pipeline "{}" already exists.'.format(pipeline_name),
                    result.output)

  def testPipelineUpdate(self):
    pipeline_name = 'chicago_taxi_beam'
    handler_pipeline_path = os.path.join(self._beam_home, pipeline_name)
    pipeline_path_1 = os.path.join(self._testdata_dir,
                                   'test_pipeline_beam_1.py')
    # Try pipeline update when pipeline does not exist.
    result = self.runner.invoke(cli_group, [
        'pipeline', 'update', '--engine', 'beam', '--pipeline_path',
        pipeline_path_1
    ])
    self.assertIn('CLI', result.output)
    self.assertIn('Updating pipeline', result.output)
    self.assertIn('Pipeline "{}" does not exist.'.format(pipeline_name),
                  result.output)
    self.assertFalse(fileio.exists(handler_pipeline_path))

    # Now update an existing pipeline.
    self._valid_create_and_check(pipeline_path_1, pipeline_name)
    pipeline_path_2 = os.path.join(self._testdata_dir,
                                   'test_pipeline_beam_2.py')
    result = self.runner.invoke(cli_group, [
        'pipeline', 'update', '--engine', 'beam', '--pipeline_path',
        pipeline_path_2
    ])
    self.assertIn('CLI', result.output)
    self.assertIn('Updating pipeline', result.output)
    self.assertIn('Pipeline "{}" updated successfully.'.format(pipeline_name),
                  result.output)
    self.assertTrue(
        fileio.exists(
            os.path.join(handler_pipeline_path, 'pipeline_args.json')))

  def testPipelineCompile(self):
    # Invalid DSL path
    pipeline_path = os.path.join(self._testdata_dir, 'test_pipeline_flink.py')
    result = self.runner.invoke(cli_group, [
        'pipeline', 'compile', '--engine', 'beam', '--pipeline_path',
        pipeline_path
    ])
    self.assertIn('CLI', result.output)
    self.assertIn('Compiling pipeline', result.output)
    self.assertIn('Invalid pipeline path: {}'.format(pipeline_path),
                  result.output)

    # Wrong Runner.
    pipeline_path = os.path.join(self.tmp_dir, 'empty_file.py')
    io_utils.write_string_file(pipeline_path, '')
    result = self.runner.invoke(cli_group, [
        'pipeline', 'compile', '--engine', 'beam', '--pipeline_path',
        pipeline_path
    ])
    self.assertIn('CLI', result.output)
    self.assertIn('Compiling pipeline', result.output)
    self.assertIn('Cannot find BeamDagRunner.run()', result.output)

    # Successful compilation.
    pipeline_path = os.path.join(self._testdata_dir, 'test_pipeline_beam_2.py')
    result = self.runner.invoke(cli_group, [
        'pipeline', 'compile', '--engine', 'beam', '--pipeline_path',
        pipeline_path
    ])
    self.assertIn('CLI', result.output)
    self.assertIn('Compiling pipeline', result.output)
    self.assertIn('Pipeline compiled successfully', result.output)

  def testPipelineDelete(self):
    pipeline_path = os.path.join(self._testdata_dir, 'test_pipeline_beam_1.py')
    pipeline_name = 'chicago_taxi_beam'
    handler_pipeline_path = os.path.join(self._beam_home, pipeline_name)

    # Try deleting a non existent pipeline.
    result = self.runner.invoke(cli_group, [
        'pipeline', 'delete', '--engine', 'beam', '--pipeline_name',
        pipeline_name
    ])
    self.assertIn('CLI', result.output)
    self.assertIn('Deleting pipeline', result.output)
    self.assertIn('Pipeline "{}" does not exist.'.format(pipeline_name),
                  result.output)
    self.assertFalse(fileio.exists(handler_pipeline_path))

    # Create a pipeline.
    self._valid_create_and_check(pipeline_path, pipeline_name)

    # Now delete the pipeline.
    result = self.runner.invoke(cli_group, [
        'pipeline', 'delete', '--engine', 'beam', '--pipeline_name',
        pipeline_name
    ])
    self.assertIn('CLI', result.output)
    self.assertIn('Deleting pipeline', result.output)
    self.assertFalse(fileio.exists(handler_pipeline_path))
    self.assertIn('Pipeline "{}" deleted successfully.'.format(pipeline_name),
                  result.output)

  def testPipelineList(self):

    # Try listing pipelines when there are none.
    result = self.runner.invoke(cli_group,
                                ['pipeline', 'list', '--engine', 'beam'])
    self.assertIn('CLI', result.output)
    self.assertIn('Listing all pipelines', result.output)
    self.assertIn('No pipelines to display.', result.output)

    # Create pipelines.
    pipeline_name_1 = 'chicago_taxi_beam'
    pipeline_path_1 = os.path.join(self._testdata_dir,
                                   'test_pipeline_beam_1.py')
    self._valid_create_and_check(pipeline_path_1, pipeline_name_1)

    pipeline_name_2 = 'chicago_taxi_beam_v2'
    pipeline_path_2 = os.path.join(self._testdata_dir,
                                   'test_pipeline_beam_3.py')
    self._valid_create_and_check(pipeline_path_2, pipeline_name_2)

    # List pipelines.
    result = self.runner.invoke(cli_group,
                                ['pipeline', 'list', '--engine', 'beam'])
    self.assertIn('CLI', result.output)
    self.assertIn('Listing all pipelines', result.output)
    self.assertIn(pipeline_name_1, result.output)
    self.assertIn(pipeline_name_2, result.output)

  def testPipelineSchema(self):
    pipeline_path = os.path.join(self._testdata_dir, 'test_pipeline_beam_2.py')
    pipeline_name = 'chicago_taxi_beam'

    # Try getting schema without creating pipeline.
    result = self.runner.invoke(cli_group, [
        'pipeline', 'schema', '--engine', 'beam', '--pipeline_name',
        pipeline_name
    ])
    self.assertIn('CLI', result.output)
    self.assertIn('Getting latest schema.', result.output)
    self.assertIn('Pipeline "{}" does not exist.'.format(pipeline_name),
                  result.output)

    # Create a pipeline.
    self._valid_create_and_check(pipeline_path, pipeline_name)

    # Try getting schema without creating a pipeline run.
    result = self.runner.invoke(cli_group, [
        'pipeline', 'schema', '--engine', 'beam', '--pipeline_name',
        pipeline_name
    ])
    self.assertIn('CLI', result.output)
    self.assertIn('Getting latest schema.', result.output)
    self.assertIn(
        'Create a run before inferring schema. If pipeline is already running, then wait for it to successfully finish.',
        result.output)

    # Run pipeline.
    self._valid_run_and_check(pipeline_name)

    # Try inferring schema without SchemaGen component.
    result = self.runner.invoke(cli_group, [
        'pipeline', 'schema', '--engine', 'beam', '--pipeline_name',
        pipeline_name
    ])
    self.assertIn('CLI', result.output)
    self.assertIn('Getting latest schema.', result.output)
    self.assertIn(
        'Either SchemaGen component does not exist or pipeline is still running. If pipeline is running, then wait for it to successfully finish.',
        result.output)

    # Create a pipeline.
    pipeline_path = os.path.join(self._testdata_dir, 'test_pipeline_beam_3.py')
    pipeline_name = 'chicago_taxi_beam_v2'
    self._valid_create_and_check(pipeline_path, pipeline_name)

    # Run pipeline
    self._valid_run_and_check(pipeline_name)

    # Infer Schema when pipeline runs for the first time.
    schema_path = os.path.join(os.getcwd(), 'schema.pbtxt')
    result = self.runner.invoke(cli_group, [
        'pipeline', 'schema', '--engine', 'beam', '--pipeline_name',
        pipeline_name
    ])
    self.assertIn('CLI', result.output)
    self.assertIn('Getting latest schema.', result.output)
    self.assertTrue(fileio.exists(schema_path))
    self.assertIn('Path to schema: {}'.format(schema_path), result.output)
    self.assertIn(
        '*********SCHEMA FOR {}**********'.format(pipeline_name.upper()),
        result.output)

  def _valid_run_and_check(self, pipeline_name):
    result = self.runner.invoke(
        cli_group,
        ['run', 'create', '--engine', 'beam', '--pipeline_name', pipeline_name])
    self.assertIn('CLI', result.output)
    self.assertNotIn('Pipeline "{}" does not exist.'.format(pipeline_name),
                     result.output)
    self.assertIn('Creating a run for pipeline: {}'.format(pipeline_name),
                  result.output)

  def testRunCreate(self):
    # Create a pipeline first.
    pipeline_name_1 = 'chicago_taxi_beam'
    pipeline_path_1 = os.path.join(self._testdata_dir,
                                   'test_pipeline_beam_2.py')
    self._valid_create_and_check(pipeline_path_1, pipeline_name_1)

    # Now run a different pipeline
    pipeline_name_2 = 'chicago_taxi_beam_v2'
    result = self.runner.invoke(cli_group, [
        'run', 'create', '--engine', 'beam', '--pipeline_name', pipeline_name_2
    ])
    self.assertIn('CLI', result.output)
    self.assertIn('Creating a run for pipeline: {}'.format(pipeline_name_2),
                  result.output)
    self.assertIn('Pipeline "{}" does not exist.'.format(pipeline_name_2),
                  result.output)

    # Now run the pipeline
    self._valid_run_and_check(pipeline_name_1)
