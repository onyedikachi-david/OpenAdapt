"""
Implements a ReplayStrategy mixin for generating LLM completions.

Usage:

    class MyReplayStrategy(LLMReplayStrategyMixin):
        ...
"""


from loguru import logger
import transformers as tf  # RIP TensorFlow

from puterbot.models import Recording
from puterbot.strategies.base import BaseReplayStrategy


MODEL_NAME = "gpt2"  # gpt2-xl is bigger and slower
MODEL_MAX_LENGTH = 1024


class LLMReplayStrategyMixin(BaseReplayStrategy):

    def __init__(
        self,
        recording: Recording,
        model_name: str = MODEL_NAME,
        model_max_length: str = MODEL_MAX_LENGTH,
    ):
        super().__init__(recording)

        logger.info(f"{model_name=}")
        self.tokenizer = tf.AutoTokenizer.from_pretrained(model_name)
        self.model = tf.AutoModelForCausalLM.from_pretrained(model_name)
        self.model_max_length = model_max_length

    def get_completion(
        self,
        prompt: str,
        max_tokens: int,
    ):
        model_max_length = self.model_max_length
        if model_max_length and len(prompt) > model_max_length:
            logger.warning(
                f"Truncating from {len(prompt)=} to {model_max_length=}"
            )
            prompt = prompt[:model_max_length]
        logger.debug(f"{prompt=} {max_tokens=}")
        input_tokens = self.tokenizer(prompt, return_tensors="pt")
        pad_token_id = self.tokenizer.eos_token_id
        attention_mask = input_tokens["attention_mask"]
        output_tokens = self.model.generate(
            input_ids=input_tokens["input_ids"],
            attention_mask=attention_mask,
            max_length=input_tokens["input_ids"].shape[-1] + max_tokens,
            pad_token_id=pad_token_id,
            num_return_sequences=1
        )
        N = input_tokens["input_ids"].shape[-1]
        completion = self.tokenizer.decode(
            output_tokens[:, N:][0],
            clean_up_tokenization_spaces=True,
        )
        logger.debug(f"{completion=}")
        return completion