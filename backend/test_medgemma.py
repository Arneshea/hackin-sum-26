import torch
from transformers import AutoProcessor, AutoModelForImageTextToText, BitsAndBytesConfig

model_id = "google/medgemma-1.5-4b-it"

quant_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.bfloat16,   # <-- the critical fix, not float16
    bnb_4bit_use_double_quant=True,
)

processor = AutoProcessor.from_pretrained(model_id)

model = AutoModelForImageTextToText.from_pretrained(
    model_id,
    quantization_config=quant_config,
    device_map={"": 0},           # <-- everything on GPU 0, NO CPU offload
    torch_dtype=torch.bfloat16,
    attn_implementation="eager",  # <-- avoids a known SDPA garbage-output bug on Gemma models
)

messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": (
                "You are a broad pre-triage assistant. You do NOT diagnose. "
                "Reply with EXACTLY ONE WORD: URGENT, CONSULT_GP, or SELF_MONITOR.\n\n"
                "Patient description: I have severe chest pain and difficulty breathing"
            )}
        ],
    }
]

inputs = processor.apply_chat_template(
    messages,
    add_generation_prompt=True,
    tokenize=True,
    return_dict=True,
    return_tensors="pt",
).to(model.device)

with torch.inference_mode():
    output = model.generate(**inputs, max_new_tokens=16, do_sample=False)

decoded = processor.batch_decode(output[:, inputs["input_ids"].shape[-1]:], skip_special_tokens=True)
print(decoded)