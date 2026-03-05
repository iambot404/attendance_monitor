# Assignment 1 — Prompting Techniques

## Overview

This assignment explores three fundamental prompting strategies used with Large Language Models (LLMs): **Zero-Shot**, **One-Shot**, and **Few-Shot** prompting.

---

## 🔹 Zero-Shot Prompting

Zero-shot prompting involves giving the model a task with **no examples**. The model relies entirely on its pre-trained knowledge to generate a response.

### What is it?
You simply describe what you want, and the model performs the task using its prior training — no demonstrations needed.

### Changed Prompt Example:
> *"Describe the concept of Artificial Intelligence as if explaining to a 10-year-old."*

No examples were provided — the model answers directly from its training.

### Math Problem (Zero-Shot):
**Prompt:** *"If a bus covers 120 km in 3 hours, what is its average speed?"*

**Solution:**
- Formula: Average Speed = Total Distance ÷ Total Time
- Average Speed = 120 ÷ 3 = **40 km/h**

✅ **Answer: 40 kilometers per hour**

---

## 🔹 One-Shot Prompting

One-shot prompting provides **one example** to guide the model on the expected format or style before asking it to complete the task.

### What is it?
A single demonstration helps the model understand the desired output format before generating its own answer.

### Changed Prompt Example:
> Translate English to Spanish.
> 
> **Example:**
> English: Good morning
> Spanish: Buenos días
> 
> **Now translate:**
> English: How are you?

One example sets the pattern for the model to follow.

### Math Problem (One-Shot):
**Prompt:**
> Solve speed problems.
> 
> **Example —** Problem: A car travels 80 miles in 4 hours. What is its average speed? Answer: 20 miles per hour.
> 
> **Now solve —** Problem: If a boat travels 90 miles in 3 hours, what is its average speed?

✅ **Answer: 30 miles per hour**

---

## 🔹 Few-Shot Prompting

Few-shot prompting provides **multiple examples (2–5+)** so the model understands patterns and context better before performing the task.

### What is it?
Several demonstrations help the model learn patterns, improving accuracy for complex or structured tasks.

### Changed Prompt Example:
> Classify the emotion in each sentence:
> 
> Sentence: I just got promoted at work! → **Happy**
> Sentence: My dog passed away today. → **Sad**
> Sentence: I can't believe they did that! → **Angry**
> 
> Sentence: I finally finished my project. → ?

### Math Problem (Few-Shot):
**Prompt:**
> Example 1 — Problem: A car travels 100 miles in 5 hours. Answer: 20 mph.
> Example 2 — Problem: A cyclist covers 60 miles in 3 hours. Answer: 20 mph.
> Example 3 — Problem: A swimmer completes 2 miles in 1 hour. Answer: 2 mph.
> 
> **Now solve —** Problem: If a plane flies 600 miles in 2 hours, what is its average speed?

✅ **Answer: 300 miles per hour**

---

## 📊 Quick Comparison Table

| Feature            | Zero-Shot      | One-Shot         | Few-Shot              |
|--------------------|----------------|------------------|-----------------------|
| Examples Provided  | 0              | 1                | 2+                    |
| Accuracy           | Medium         | High             | Very High             |
| Token Usage        | Low            | Medium           | High                  |
| Best For           | Simple tasks   | Structured tasks | Complex pattern tasks |

---

## 📝 Summary

| Prompting Type | Key Idea                        | Example Task                        |
|----------------|---------------------------------|-------------------------------------|
| Zero-Shot      | No examples, direct instruction | Explain AI to a 10-year-old         |
| One-Shot       | One guiding example             | Translate English → Spanish         |
| Few-Shot       | Multiple examples for pattern   | Classify emotions / Solve math      |

---

*Submitted by: iambot404 | Date: 2026-03-05*