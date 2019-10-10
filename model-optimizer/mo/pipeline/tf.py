"""
 Copyright (c) 2018-2019 Intel Corporation

 Licensed under the Apache License, Version 2.0 (the "License");
 you may not use this file except in compliance with the License.
 You may obtain a copy of the License at

      http://www.apache.org/licenses/LICENSE-2.0

 Unless required by applicable law or agreed to in writing, software
 distributed under the License is distributed on an "AS IS" BASIS,
 WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
 See the License for the specific language governing permissions and
 limitations under the License.
"""

import argparse
import logging as log

import tensorflow as tf

from mo.front.common.register_custom_ops import check_for_duplicates
from mo.front.common.register_custom_ops import update_extractors_with_extensions
from mo.front.extractor import restore_edges, extract_node_attrs, remove_control_dependency_inputs
from mo.front.tf.extractor import get_tf_edges, tf_op_extractor, tf_op_extractors
from mo.front.tf.loader import load_tf_graph_def, protobuf2nx
from mo.pipeline.common import prepare_emit_ir
from mo.utils import class_registration, tensorboard
from mo.utils.cli_parser import get_meta_info
from mo.utils.error import Error
from mo.utils.utils import refer_to_faq_msg

try:
    import tensorflow.contrib
except:
    pass  # we try to import contrib for loading models that use contrib operations


def tf2nx(argv: argparse.Namespace, model_file_name: str, output_model_name: str, output_dir: str, is_binary: bool):
    """
    Convert TF GraphDef object to NetworkX representation.
    The resulting graph is still TF-specific and needs normalization passes to be applied.
    The specific TF structure assumes each GraphDef node is converted to a single
    NetworkX node, node id is an original TF node name, and edges go directly from one op   to another op.
    """
    meta_info = get_meta_info(argv)

    if argv.tensorflow_custom_layer_libraries:
        libraries = argv.tensorflow_custom_layer_libraries.split(',')
        for library in libraries:
            log.info('Loading library "{}" with custom operations'.format(library))
            tf.load_op_library(library)

    graph_def, variables_values = load_tf_graph_def(graph_file_name=model_file_name, is_binary=is_binary,
                                                    checkpoint=argv.input_checkpoint,
                                                    user_output_node_names_list=argv.output,
                                                    model_dir=argv.saved_model_dir,
                                                    meta_graph_file=argv.input_meta_graph,
                                                    saved_model_tags=argv.saved_model_tags)

    try:
        tf.import_graph_def(graph_def, name='')
    except:
        log.warning("TensorFlow post-processing of loaded model was unsuccessful. "
                    "This is an optional step that Model Optimizer performs for any input model but it is not usually "
                    "required for all models."
                    "It likely means that the original model is ill-formed. "
                    "Model Optimizer will continue converting this model.")

    log.debug("Number of nodes in graph_def: {}".format(len(graph_def.node)))  # pylint: disable=no-member

    if argv.tensorboard_logdir:
        tensorboard.dump_for_tensorboard(graph_def, argv.tensorboard_logdir)

    update_extractors_with_extensions(tf_op_extractors)

    try:
        graph = protobuf2nx(graph_def)
        graph.__setattr__('name', output_model_name)
        # 'layout' parameter change may cause an issue in EltwiseInputReshape replacer
        # and convert_nhwc_to_nchw(graph)
        graph.graph['layout'] = 'NCHW' if argv.disable_nhwc_to_nchw else 'NHWC'
        graph.graph['cmd_params'] = argv
        graph.graph['fw'] = 'tf'

        if graph.graph['cmd_params'].generate_experimental_IR_V10:
            version = 10
        else:
            version = 6
        graph.graph['ir_version'] = 2 if argv.generate_deprecated_IR_V2 else version

        graph.graph['variables_values'] = variables_values
        del variables_values

        graph = restore_edges(graph, get_tf_edges)
        graph = remove_control_dependency_inputs(graph)
    except Exception as e:
        raise Error(
            'Cannot pre-process TensorFlow graph after reading from model file "{}". ' \
            'File is corrupt or has unsupported format. Details: {}. ' +
            refer_to_faq_msg(44),
            model_file_name,
            str(e)
        ) from e

    graph.check_empty_graph('protobuf2nx. It may happen due to problems with loaded model')
    extract_node_attrs(graph, lambda node: tf_op_extractor(node, check_for_duplicates(tf_op_extractors)))

    # --------------------------------- LOAD END ------------------------------------------------------

    class_registration.apply_replacements(graph, [
        class_registration.ClassType.FRONT_REPLACER,
        class_registration.ClassType.MIDDLE_REPLACER,
        class_registration.ClassType.BACK_REPLACER
    ])

    prepare_emit_ir(graph=graph, data_type=argv.data_type, output_dir=output_dir, output_model_name=output_model_name,
                    meta_info=meta_info)
    return 0
