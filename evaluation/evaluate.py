from dotenv import load_dotenv
load_dotenv()
from langsmith import evaluate, Client
from pydantic import BaseModel
from db_query_agent import run_medquery
# 1. Create and/or select your dataset
client = Client()
dataset_name = "golden_dataset"
from langchain.chat_models import init_chat_model
class CorrectnessScore(BaseModel):
    score: bool

# 2. Define an evaluator
def correctness(inputs: dict, outputs: dict, reference_outputs: dict) -> bool:
    question         = inputs.get("question", "")
    model_output     = outputs.get("output", "")
    reference_answer = reference_outputs.get("final_answer", "")  # ✅ Fix 1: correct key

    prompt = """
    You are an expert data labeler evaluating model outputs for correctness. Your task is to assign a score based on the following rubric:

    <Rubric>
        A correct answer:
        - Provides accurate information
        - Uses suitable analogies and examples
        - Contains no factual errors
        - Is logically consistent

        When scoring, you should penalize:
        - Factual errors
        - Incoherent analogies and examples
        - Logical inconsistencies
    </Rubric>

    <Instructions>
        - Carefully read the input and output
        - Use the reference output to determine if the model output contains errors
        - Focus whether the model output uses accurate analogies and is logically consistent
    </Instructions>

    <Reminder>
        The analogies in the output do not need to match the reference output exactly. Focus on logical consistency.
    </Reminder>

    <input>
        {}
    </input>

    <output>
        {}
    </output>

    Use the reference outputs below to help you evaluate the correctness of the response:
    <reference_outputs>
        {}
    </reference_outputs>
    """.format(question, model_output, reference_answer)

    llm = init_chat_model("gpt-5.6-luna", model_provider="openai",reasoning_effort="none" )
    structured_llm = llm.with_structured_output(CorrectnessScore)  # ✅ Fix 2: structured output
    generation = structured_llm.invoke(prompt)
    return generation.score

# 3. Define a function to run your application
def run(inputs: dict, config: dict = None) -> dict:
    answer = run_medquery(
        user_question=inputs["question"],
        config=config  # langsmith trace config passes through
    )
    return {"output": answer}

evaluate(
    run,
    data=dataset_name,
    evaluators=[correctness],
    experiment_prefix="golden_dataset experiment-1"
)