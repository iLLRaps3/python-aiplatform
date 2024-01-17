from typing import Optional, Union

from google.cloud import aiplatform
from google.cloud.aiplatform import initializer as aiplatform_initializer
from vertexai.language_models import _language_models
from vertexai.language_models import _language_models as tuning


class DistillationMixin:
    _DISTILLATION_PIPELINE_URI = (
        "https://us-kfp.pkg.dev/ml-pipeline/distillation/distillation/v1.0.0"
    )

    def distill_from(
        self,
        *,
        dataset: str,
        teacher_model: Union[str, _language_models._TextGenerationModel],
        train_steps: Optional[int] = None,
        learning_rate_multiplier: Optional[float] = None,
        evaluation_spec: Optional[tuning.TuningEvaluationSpec] = None,
        accelerator_type: Optional[tuning._ACCELERATOR_TYPE_TYPE] = None,
        model_display_name: Optional[str] = None,
    ):
        """Tunes a smaller model with help from another bigger model.

        Args:
            dataset: A URI pointing to data in JSON lines format.
            teacher_model: The teacher model to use for distillation.
            train_steps: Number of training batches to use (batch size is 8 samples).
            learning_rate_multiplier: Learning rate multiplier to use in tuning.
            evaluation_spec: Specification for the model evaluation during tuning.
            accelerator_type: Type of accelerator to use. Can be "TPU" or "GPU".
            model_display_name: Custom display name for the tuned model.

        Returns:
            A tuning job for distillation.

        Raises:
            RuntimeError: If the model does not support distillation.
        """
        if "/models/" not in self._endpoint_name:
            raise RuntimeError(
                f"Model does not support distillation: {self._endpoint_name}"
            )
        student_short_model_id = self._endpoint_name.split("/")[-1]

        if isinstance(teacher_model, str):
            teacher_short_model_id = teacher_model
        elif isinstance(teacher_model, _language_models._LanguageModel):
            if "/models/" not in teacher_model._endpoint_name:
                raise RuntimeError(
                    f"Teacher model does not support distillation: {teacher_model._endpoint_name}"
                )
            teacher_short_model_id = teacher_model._endpoint_name.split("/")[-1]
        else:
            raise RuntimeError(f"Unsupported teacher model type: {teacher_model}")

        pipeline_arguments = {
            "teacher_model_reference": teacher_short_model_id,
            "student_model_reference": student_short_model_id,
            "dataset_uri": dataset,
            "project": aiplatform_initializer.global_config.project,
            "location": aiplatform_initializer.global_config.location,
        }
        if train_steps is not None:
            pipeline_arguments["train_steps"] = train_steps
        if learning_rate_multiplier is not None:
            pipeline_arguments["learning_rate_multiplier"] = learning_rate_multiplier
        if evaluation_spec is not None:
            pipeline_arguments["evaluation_data_uri"] = evaluation_spec.evaluation_data
            pipeline_arguments[
                "evaluation_interval"
            ] = evaluation_spec.evaluation_interval
            pipeline_arguments[
                "enable_early_stopping"
            ] = evaluation_spec.enable_early_stopping
            pipeline_arguments[
                "enable_checkpoint_selection"
            ] = evaluation_spec.enable_checkpoint_selection
            pipeline_arguments["tensorboard_resource_id"] = evaluation_spec.tensorboard
            # pipeline_parameter_values["evaluation_output_root_dir"] = ...
        if accelerator_type is not None:
            pipeline_arguments["accelerator_type"] = accelerator_type
        if aiplatform_initializer.global_config.encryption_spec_key_name is not None:
            pipeline_arguments[
                "encryption_spec_key_name"
            ] = aiplatform_initializer.global_config.encryption_spec_key_name
        if model_display_name is None:
            model_display_name = (
                f"{student_short_model_id}"
                f" distilled from {teacher_short_model_id}"
            )
        pipeline_arguments["model_display_name"] = model_display_name
        # # Not exposing these parameters:
        # temperature: Optional[float] = None,
        # max_context_length: Optional[int] = None,
        # tpu_training_skip_cmek: Optional[bool] = None,
        # api_endpoint: Optional[str] = None,
        # version: Optional[str] = None,
        pipeline_job = aiplatform.PipelineJob(
            template_path=self._DISTILLATION_PIPELINE_URI,
            display_name=None,
            parameter_values=pipeline_arguments,
        )
        pipeline_job.submit()
        tuning_job = tuning._LanguageModelTuningJob(
            base_model=self,
            job=pipeline_job,
        )
        return tuning_job