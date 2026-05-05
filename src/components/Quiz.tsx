import { useMemo, useState } from "react";

type Option = "A" | "B" | "C" | "D";

interface Question {
  id: string;
  type: string;
  question: string;
  options: Record<Option, string>;
  correct: Option;
  explanationZh: string;
}

interface Props {
  questions: Question[];
}

const TYPE_LABEL_ZH: Record<string, string> = {
  detail: "細節 Detail",
  inference: "推論 Inference",
  vocabulary: "單字情境 Vocabulary",
  main_idea: "主旨 Main Idea",
};

export default function Quiz({ questions }: Props) {
  const [answers, setAnswers] = useState<Record<string, Option | undefined>>(
    {}
  );
  const [submitted, setSubmitted] = useState(false);

  const score = useMemo(() => {
    if (!submitted) return 0;
    return questions.filter((q) => answers[q.id] === q.correct).length;
  }, [submitted, answers, questions]);

  const allAnswered = questions.every((q) => answers[q.id]);

  const handleSelect = (qid: string, opt: Option) => {
    if (submitted) return;
    setAnswers((prev) => ({ ...prev, [qid]: opt }));
  };

  const handleReset = () => {
    setAnswers({});
    setSubmitted(false);
  };

  return (
    <section className="mt-12 border-t border-stone-200 dark:border-stone-800 pt-10">
      <div className="flex items-baseline justify-between flex-wrap gap-2 mb-6">
        <h2 className="text-2xl font-bold tracking-tight">
          選擇題練習 · Quiz
        </h2>
        <p className="text-sm text-stone-500 dark:text-stone-400">
          共 {questions.length} 題
        </p>
      </div>

      <ol className="space-y-8">
        {questions.map((q, idx) => {
          const userAns = answers[q.id];
          const isCorrect = submitted && userAns === q.correct;
          const isWrong = submitted && userAns && userAns !== q.correct;
          return (
            <li key={q.id} className="space-y-3">
              <div className="flex items-start gap-2">
                <span className="text-xs px-2 py-0.5 rounded bg-stone-100 dark:bg-stone-800 text-stone-600 dark:text-stone-300 mt-1 shrink-0">
                  {TYPE_LABEL_ZH[q.type] ?? q.type}
                </span>
              </div>
              <p className="font-medium text-stone-900 dark:text-stone-100 leading-snug">
                <span className="mr-1">{idx + 1}.</span>
                {q.question}
              </p>
              <ul className="space-y-2">
                {(["A", "B", "C", "D"] as Option[]).map((opt) => {
                  const selected = userAns === opt;
                  const isThisCorrect = submitted && opt === q.correct;
                  const isThisWrongPick = submitted && selected && opt !== q.correct;
                  return (
                    <li key={opt}>
                      <button
                        type="button"
                        onClick={() => handleSelect(q.id, opt)}
                        disabled={submitted}
                        className={[
                          "w-full text-left rounded-md border px-3 py-2.5 text-sm transition flex gap-3 items-start",
                          "disabled:cursor-default",
                          submitted
                            ? isThisCorrect
                              ? "border-green-500 bg-green-50 dark:bg-green-900/20"
                              : isThisWrongPick
                                ? "border-red-500 bg-red-50 dark:bg-red-900/20"
                                : "border-stone-200 dark:border-stone-800 opacity-70"
                            : selected
                              ? "border-stone-800 dark:border-stone-300 bg-stone-50 dark:bg-stone-900"
                              : "border-stone-200 dark:border-stone-800 hover:border-stone-400 dark:hover:border-stone-600",
                        ].join(" ")}
                      >
                        <span className="font-semibold w-5 shrink-0">{opt}.</span>
                        <span className="flex-1">{q.options[opt]}</span>
                        {submitted && isThisCorrect && (
                          <span className="shrink-0 text-green-600 dark:text-green-400 text-xs font-medium">
                            ✓ 正解
                          </span>
                        )}
                        {submitted && isThisWrongPick && (
                          <span className="shrink-0 text-red-600 dark:text-red-400 text-xs font-medium">
                            ✗ 你選的
                          </span>
                        )}
                      </button>
                    </li>
                  );
                })}
              </ul>

              {submitted && (
                <div
                  className={[
                    "mt-3 rounded-md border p-3 text-sm leading-relaxed",
                    isCorrect
                      ? "border-green-200 dark:border-green-800 bg-green-50/50 dark:bg-green-900/10"
                      : "border-red-200 dark:border-red-800 bg-red-50/50 dark:bg-red-900/10",
                  ].join(" ")}
                >
                  <div className="font-medium mb-1">
                    {isCorrect ? "答對了！" : isWrong ? "答錯了。" : ""}
                    <span className="text-stone-500 dark:text-stone-400 font-normal">
                      （正解 {q.correct}）
                    </span>
                  </div>
                  <p className="text-stone-700 dark:text-stone-300">
                    {q.explanationZh}
                  </p>
                </div>
              )}
            </li>
          );
        })}
      </ol>

      <div className="mt-8 flex flex-wrap gap-3 items-center">
        {!submitted ? (
          <button
            type="button"
            onClick={() => setSubmitted(true)}
            disabled={!allAnswered}
            className="px-5 py-2 rounded-md bg-stone-900 text-white dark:bg-stone-100 dark:text-stone-900 font-medium disabled:opacity-50 disabled:cursor-not-allowed hover:opacity-90 transition"
          >
            提交答案 · Submit
          </button>
        ) : (
          <>
            <div className="text-lg font-semibold">
              你的成績：{score} / {questions.length}
            </div>
            <button
              type="button"
              onClick={handleReset}
              className="px-4 py-2 rounded-md border border-stone-300 dark:border-stone-700 text-sm hover:bg-stone-50 dark:hover:bg-stone-900 transition"
            >
              重做一次
            </button>
          </>
        )}
        {!submitted && !allAnswered && (
          <span className="text-sm text-stone-500 dark:text-stone-400">
            請回答全部 {questions.length} 題後再提交
          </span>
        )}
      </div>
    </section>
  );
}
