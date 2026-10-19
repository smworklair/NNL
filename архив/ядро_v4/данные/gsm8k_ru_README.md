---
annotations_creators:
- crowdsourced
language_creators:
- translated
language:
- ru
license:
- mit
multilinguality:
- monolingual
size_categories:
- 1K<n<10K
source_datasets:
- gsm8k
task_categories:
- text2text-generation
task_ids: []
paperswithcode_id: gsm8k
pretty_name: Grade School Math 8K (ru)
tags:
- math-word-problems
configs:
- config_name: default
  data_files:
  - split: train
    path: data/train-*
  - split: test
    path: data/test-*
dataset_info:
  features:
  - name: question
    dtype: string
  - name: answer
    dtype: string
  splits:
  - name: train
    num_bytes: 6815618.0
    num_examples: 7473
  - name: test
    num_bytes: 1234140.0
    num_examples: 1319
  download_size: 3883654
  dataset_size: 8049758.0
---
# gsm8k-ru

Translated version of [gsm8k](https://huggingface.co/datasets/gsm8k) dataset into Russian.

## Dataset Description

- **Homepage:** https://openai.com/blog/grade-school-math/
- **Repository:** https://github.com/openai/grade-school-math
- **Paper:** https://arxiv.org/abs/2110.14168