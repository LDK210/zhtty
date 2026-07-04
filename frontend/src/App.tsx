import { useEffect, useMemo, useState } from "react";
import { BriefcaseBusiness, FileText, Play, RefreshCw, Upload } from "lucide-react";
import { createJob, getJob, getLogs, getResults, listJobs, runJob, uploadResumes } from "./api";
import type { AgentLog, Candidate, Job, JobStatus, ResumeStatus } from "./types";

const statusLabels: Record<JobStatus | ResumeStatus, string> = {
  draft: "草稿",
  ready: "就绪",
  running: "运行中",
  completed: "已完成",
  failed: "失败",
  uploaded: "已上传",
  extracting: "提取中",
  parsed: "已解析",
  scored: "已评分",
};

const statusClass: Record<string, string> = {
  draft: "bg-slate-400",
  ready: "bg-brand",
  running: "bg-warning",
  completed: "bg-success",
  failed: "bg-danger",
  uploaded: "bg-slate-500",
  extracting: "bg-warning",
  parsed: "bg-brand",
  scored: "bg-brand",
};

export function App() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [selectedJobId, setSelectedJobId] = useState<number | null>(null);
  const [selectedJob, setSelectedJob] = useState<Job | null>(null);
  const [results, setResults] = useState<Candidate[]>([]);
  const [logs, setLogs] = useState<AgentLog[]>([]);
  const [selectedCandidate, setSelectedCandidate] = useState<Candidate | null>(null);
  const [title, setTitle] = useState("后端开发实习生");
  const [jdText, setJdText] = useState("要求：熟悉 Java / Spring Boot / MySQL / Redis，有项目经验，了解 Docker 优先。");
  const [files, setFiles] = useState<FileList | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function refreshJobs() {
    const data = await listJobs();
    setJobs(data);
    if (!selectedJobId && data[0]) {
      setSelectedJobId(data[0].id);
    }
  }

  async function refreshDetail(jobId: number) {
    const [job, ranking, agentLogs] = await Promise.all([getJob(jobId), getResults(jobId), getLogs(jobId)]);
    setSelectedJob(job);
    setResults(ranking);
    setLogs(agentLogs);
  }

  useEffect(() => {
    refreshJobs().catch((error) => setMessage(error.message));
  }, []);

  useEffect(() => {
    if (!selectedJobId) return;
    refreshDetail(selectedJobId).catch((error) => setMessage(error.message));
    const timer = window.setInterval(() => {
      refreshDetail(selectedJobId).catch(() => undefined);
    }, 2500);
    return () => window.clearInterval(timer);
  }, [selectedJobId]);

  const progressTotal = useMemo(() => {
    if (!selectedJob) return 0;
    return Object.values(selectedJob.progress).reduce((sum, value) => sum + value, 0);
  }, [selectedJob]);

  async function handleCreate() {
    setBusy(true);
    setMessage("");
    try {
      const job = await createJob(title, jdText);
      if (files?.length) {
        await uploadResumes(job.id, files);
      }
      await refreshJobs();
      setSelectedJobId(job.id);
      setMessage("任务已创建");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "创建失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleUpload() {
    if (!selectedJobId || !files?.length) return;
    setBusy(true);
    try {
      await uploadResumes(selectedJobId, files);
      await refreshDetail(selectedJobId);
      await refreshJobs();
      setMessage("简历已上传");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "上传失败");
    } finally {
      setBusy(false);
    }
  }

  async function handleRun() {
    if (!selectedJobId) return;
    setBusy(true);
    try {
      await runJob(selectedJobId);
      await refreshDetail(selectedJobId);
      await refreshJobs();
      setMessage("筛选任务已启动");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "启动失败");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="min-h-screen">
      <header className="border-b border-line bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded bg-ink text-white">
              <BriefcaseBusiness size={21} />
            </div>
            <div>
              <h1 className="text-xl font-semibold tracking-normal">HirePilot</h1>
              <p className="text-sm text-muted">AI 简历筛选 + 面试邀约 Agent</p>
            </div>
          </div>
          <button className="inline-flex items-center gap-2 rounded border border-line bg-white px-3 py-2 text-sm" onClick={refreshJobs}>
            <RefreshCw size={16} /> 刷新
          </button>
        </div>
      </header>

      <div className="mx-auto grid max-w-7xl grid-cols-12 gap-5 px-6 py-6">
        <section className="col-span-12 lg:col-span-4">
          <Panel title="新建招聘任务">
            <label className="block text-sm font-medium">岗位名称</label>
            <input className="mt-1 w-full rounded border border-line px-3 py-2" value={title} onChange={(event) => setTitle(event.target.value)} />
            <label className="mt-4 block text-sm font-medium">岗位 JD</label>
            <textarea
              className="mt-1 min-h-32 w-full resize-y rounded border border-line px-3 py-2"
              value={jdText}
              onChange={(event) => setJdText(event.target.value)}
            />
            <label className="mt-4 block text-sm font-medium">简历文件</label>
            <input
              className="mt-1 w-full rounded border border-line bg-white px-3 py-2"
              type="file"
              multiple
              accept=".pdf,.docx"
              onChange={(event) => setFiles(event.target.files)}
            />
            <button
              className="mt-4 inline-flex w-full items-center justify-center gap-2 rounded bg-brand px-4 py-2 font-medium text-white disabled:opacity-50"
              disabled={busy}
              onClick={handleCreate}
            >
              <FileText size={17} /> 创建任务
            </button>
          </Panel>

          <Panel title="历史任务" className="mt-5">
            <div className="space-y-2">
              {jobs.map((job) => (
                <button
                  key={job.id}
                  className={`w-full rounded border px-3 py-3 text-left ${selectedJobId === job.id ? "border-brand bg-blue-50" : "border-line bg-white"}`}
                  onClick={() => setSelectedJobId(job.id)}
                >
                  <div className="flex items-center justify-between gap-3">
                    <span className="font-medium">{job.title}</span>
                    <StatusBadge status={job.status} />
                  </div>
                  <p className="mt-1 text-xs text-muted">{new Date(job.created_at).toLocaleString()}</p>
                </button>
              ))}
              {!jobs.length && <p className="text-sm text-muted">暂无任务</p>}
            </div>
          </Panel>
        </section>

        <section className="col-span-12 lg:col-span-8">
          {message && <div className="mb-4 rounded border border-line bg-white px-4 py-3 text-sm text-muted">{message}</div>}
          {selectedJob ? (
            <>
              <Panel title={selectedJob.title}>
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <StatusBadge status={selectedJob.status} />
                    <p className="mt-2 max-w-3xl text-sm text-muted">{selectedJob.jd_text}</p>
                    {selectedJob.error_message && <p className="mt-2 text-sm text-danger">{selectedJob.error_message}</p>}
                  </div>
                  <div className="flex gap-2">
                    <button className="inline-flex items-center gap-2 rounded border border-line bg-white px-3 py-2 text-sm" onClick={handleUpload} disabled={busy}>
                      <Upload size={16} /> 追加简历
                    </button>
                    <button className="inline-flex items-center gap-2 rounded bg-ink px-3 py-2 text-sm text-white" onClick={handleRun} disabled={busy}>
                      <Play size={16} /> 开始筛选
                    </button>
                  </div>
                </div>

                <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
                  <Metric label="简历总数" value={progressTotal} />
                  <Metric label="已完成" value={selectedJob.progress.completed || 0} />
                  <Metric label="处理中" value={(selectedJob.progress.extracting || 0) + (selectedJob.progress.parsed || 0) + (selectedJob.progress.scored || 0)} />
                  <Metric label="失败" value={selectedJob.progress.failed || 0} />
                </div>

                <div className="mt-5 overflow-hidden rounded border border-line">
                  <table className="w-full border-collapse text-sm">
                    <thead className="bg-panel text-left text-muted">
                      <tr>
                        <th className="px-3 py-2">文件</th>
                        <th className="px-3 py-2">状态</th>
                        <th className="px-3 py-2">错误</th>
                      </tr>
                    </thead>
                    <tbody>
                      {selectedJob.resumes.map((resume) => (
                        <tr key={resume.id} className="border-t border-line">
                          <td className="px-3 py-2">{resume.original_filename}</td>
                          <td className="px-3 py-2"><StatusBadge status={resume.status} /></td>
                          <td className="px-3 py-2 text-danger">{resume.error_message || "-"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </Panel>

              <Panel title="候选人排名" className="mt-5">
                <div className="space-y-3">
                  {results.map((candidate) => (
                    <button
                      key={candidate.id}
                      className="w-full rounded border border-line bg-white p-4 text-left hover:border-brand"
                      onClick={() => setSelectedCandidate(candidate)}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="text-lg font-semibold">{candidate.name}</div>
                          <div className="mt-1 text-sm text-muted">{candidate.structured_json.skills?.join(" / ") || "暂无技能标签"}</div>
                        </div>
                        <div className="text-right">
                          <div className="text-2xl font-semibold">{candidate.score.total_score}</div>
                          <div className="text-sm text-muted">{candidate.score.level}</div>
                        </div>
                      </div>
                      <p className="mt-3 text-sm text-muted">{candidate.score.summary}</p>
                    </button>
                  ))}
                  {!results.length && <p className="text-sm text-muted">暂无评分结果</p>}
                </div>
              </Panel>

              <Panel title="Agent 日志" className="mt-5">
                <div className="max-h-80 space-y-2 overflow-auto">
                  {logs.map((log) => (
                    <div key={log.id} className="rounded border border-line bg-white px-3 py-2 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-medium">{log.step}</span>
                        <span className="text-xs text-muted">{new Date(log.created_at).toLocaleTimeString()}</span>
                      </div>
                      <p className="mt-1 text-muted">{log.message}</p>
                    </div>
                  ))}
                  {!logs.length && <p className="text-sm text-muted">暂无日志</p>}
                </div>
              </Panel>
            </>
          ) : (
            <Panel title="任务详情">
              <p className="text-sm text-muted">请选择或创建一个招聘任务</p>
            </Panel>
          )}
        </section>
      </div>

      {selectedCandidate && <CandidateDrawer candidate={selectedCandidate} onClose={() => setSelectedCandidate(null)} />}
    </main>
  );
}

function Panel({ title, className = "", children }: { title: string; className?: string; children: React.ReactNode }) {
  return (
    <section className={`rounded border border-line bg-white p-5 ${className}`}>
      <h2 className="mb-4 text-base font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded border border-line bg-panel px-4 py-3">
      <div className="text-2xl font-semibold">{value}</div>
      <div className="text-sm text-muted">{label}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: JobStatus | ResumeStatus }) {
  return (
    <span className="inline-flex items-center gap-2 rounded border border-line bg-white px-2 py-1 text-xs text-muted">
      <span className={`status-dot ${statusClass[status] || "bg-slate-400"}`} />
      {statusLabels[status] || status}
    </span>
  );
}

function CandidateDrawer({ candidate, onClose }: { candidate: Candidate; onClose: () => void }) {
  return (
    <div className="fixed inset-0 z-20 bg-black/30 p-4" onClick={onClose}>
      <aside className="ml-auto h-full max-w-2xl overflow-auto rounded bg-white p-6 shadow-xl" onClick={(event) => event.stopPropagation()}>
        <div className="flex items-start justify-between gap-4">
          <div>
            <h2 className="text-xl font-semibold">{candidate.name}</h2>
            <p className="mt-1 text-sm text-muted">{candidate.email || "无邮箱"} · {candidate.phone || "无电话"}</p>
          </div>
          <button className="rounded border border-line px-3 py-1 text-sm" onClick={onClose}>关闭</button>
        </div>
        <div className="mt-5 grid grid-cols-2 gap-3">
          {Object.entries(candidate.score.score_detail_json).map(([key, value]) => (
            <Metric key={key} label={key} value={value} />
          ))}
        </div>
        <DetailBlock title="匹配点" items={candidate.score.matched_points_json} />
        <DetailBlock title="不足点" items={candidate.score.missing_points_json} />
        <DetailBlock title="面试问题" items={candidate.score.interview_questions_json} />
        <section className="mt-5 rounded border border-line bg-panel p-4">
          <h3 className="font-semibold">邀约文案</h3>
          <p className="mt-2 text-sm leading-6 text-muted">{candidate.score.invitation_message}</p>
        </section>
      </aside>
    </div>
  );
}

function DetailBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="mt-5 rounded border border-line bg-white p-4">
      <h3 className="font-semibold">{title}</h3>
      <ul className="mt-2 space-y-2 text-sm text-muted">
        {(items.length ? items : ["暂无"]).map((item, index) => (
          <li key={`${item}-${index}`}>{item}</li>
        ))}
      </ul>
    </section>
  );
}
