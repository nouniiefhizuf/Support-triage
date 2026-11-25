# Data and model notices

The app downloads the Bitext Customer Support Training Dataset from Hugging Face at first launch and stores a local SQLite copy. Dataset card: https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset. The dataset card identifies the license as CDLA-Sharing-1.0. The app does not redistribute a copy in this source archive. The dataset is used for retrieval examples and is not an authoritative business policy.

The default Ollama model is `qwen3:1.7b`. Install/use it according to the terms displayed by Ollama. No model weights are bundled with the project.

When configured, the app transmits only the human-approved reply text to `soltaniahmed3000@gmail.com` through the sending Gmail account's SMTP service. Gmail credentials must be provided locally in `.env`; the project does not contain them. See README.md for setup and Google's App Password guidance.
