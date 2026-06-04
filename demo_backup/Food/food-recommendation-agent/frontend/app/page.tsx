"use client";

/* eslint-disable @next/next/no-img-element */

import { FormEvent, useEffect, useMemo, useRef, useState } from "react";

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

type Recommendation = {
  url: string;
  name: string;
  brand: string;
  category: string | string[];
  price: string | number;
  parsed_price: number;
  new_price: number;
  voucher: number;
  rating: number;
  distance_km: number;
  prep_time_minutes: number;
  estimated_time_minutes?: number;
  sold_count: number;
  image_urls: string[];
  ingredients: unknown[];
  origin: string;
  product_info: string;
  description: string;
  product_code: string;
  error: unknown;
  reason: string;
};

type ReactTraceStep = {
  step: "Thought" | "Action" | "Observation";
  content?: unknown;
  tool?: string;
  input?: unknown;
};

type ChatResponse = {
  session_id: string;
  intent: string;
  old_intent?: string | null;
  answer: string;
  recommendations: Recommendation[];
  suggested_questions: string[];
  react_trace: ReactTraceStep[];
};

const quickPrompts = [
  "Dưới 60k",
  "Trên 3 sao",
  "Giao nhanh",
  "Ít hơn 30 phút cơ",
  "Gợi ý món ăn",
  "List ngẫu nhiên",
  "Thêm Món Canh nữa",
  "Đổi sang Salad",
  "Tôi muốn món giá rẻ hơn",
  "Tôi muốn món rating cao hơn",
  "Cho tôi link món số 1",
];

const defaultSuggestedQuestions = [
  "Gợi ý món ăn dưới 60k",
  "Tôi muốn Món Canh giao dưới 30 phút",
  "Tôi muốn TRÁI CÂY",
  "Tôi muốn món trên 3 sao",
];

const categoryPrompts = [
  "BÁNH & ĐỒ ĂN VẶT",
  "BÚN TRỨNG ĐẬU DƯA CÀ",
  "Bò, bê",
  "Cá",
  "Củ quả",
  "Gia Vị, Sốt, Chấm",
  "Gia cầm",
  "Gia vị",
  "Gia vị tươi",
  "Gà, gia cầm",
  "Gạo, mỳ, miến",
  "Hải sản",
  "Khác",
  "Lương thực",
  "Lợn",
  "MÂM CỖ RẰM LỄ",
  "MÓN ĂN NẤU CHÍN SẴN",
  "Món Canh",
  "Món Chiên Xào",
  "Món Hấp, Hầm",
  "Món Kho, Rang",
  "Món Nướng",
  "Món Sốt",
  "Nấm/Măng",
  "Nộm",
  "RAU, CỦ, QUẢ",
  "Rau Củ Quả",
  "Rau xanh",
  "Rau, Củ Gia Vị",
  "Rau, Củ Sơ Chế Sẵn",
  "RẰM & LỄ",
  "Salad",
  "Set món ăn",
  "TRÁI CÂY",
  "Thịt bê",
  "Thịt bò",
  "Thịt gà",
  "Thịt heo/lợn",
  "Thủy, Hải Sản",
  "Thực phẩm chế biến",
  "Thực phẩm khác",
  "Thực phẩm khô",
  "Thực phẩm tươi sống",
  "ĐỒ CÚNG",
  "Đồ Khô, Hạt, Măng, Nấm",
  "Ếch",
];

function formatVnd(value: number | string | null | undefined) {
  const amount = Number(value);
  if (Number.isNaN(amount)) return "Chưa có";
  return `${Math.round(amount).toLocaleString("vi-VN")}đ`;
}

function formatOriginalPrice(value: string | number) {
  if (typeof value === "number") return formatVnd(value);
  return value || "Chưa có";
}

function traceValue(value: unknown) {
  if (value === undefined || value === null) return "";
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}

function formatCategory(category: Recommendation["category"]) {
  if (Array.isArray(category)) return category.filter(Boolean).join(", ") || "Khác";
  return category || "Khác";
}

function getEstimatedTime(item: Recommendation) {
  if (typeof item.estimated_time_minutes === "number" && item.estimated_time_minutes > 0) {
    return Math.round(item.estimated_time_minutes);
  }

  const distanceKm = Number(item.distance_km);
  const prepMinutes = Number(item.prep_time_minutes);
  const safeDistance = Number.isFinite(distanceKm) && distanceKm > 0 ? distanceKm : 3;
  const safePrep = Number.isFinite(prepMinutes) && prepMinutes > 0 ? prepMinutes : 15;
  return Math.round(safePrep + (safeDistance / 30) * 60);
}

export default function Home() {
  const apiUrl = useMemo(
    () => process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
    [],
  );
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [recommendations, setRecommendations] = useState<Recommendation[]>([]);
  const [suggestedQuestions, setSuggestedQuestions] = useState<string[]>(defaultSuggestedQuestions);
  const [trace, setTrace] = useState<ReactTraceStep[]>([]);
  const [traceOpen, setTraceOpen] = useState(true);
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState("");
  const messagesEndRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  async function createNewSession() {
    setLoading(true);
    setStatusText("");
    try {
      const response = await fetch(`${apiUrl}/sessions/new`, { method: "POST" });
      if (!response.ok) throw new Error("Không tạo được chat mới.");
      const data: { session_id: string } = await response.json();
      setSessionId(data.session_id);
      setMessages([]);
      setRecommendations([]);
      setSuggestedQuestions(defaultSuggestedQuestions);
      setTrace([]);
      setInput("");
    } catch (error) {
      setStatusText(error instanceof Error ? error.message : "Có lỗi khi tạo chat mới.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    createNewSession();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function sendMessage(messageText?: string) {
    const content = (messageText ?? input).trim();
    if (!content || loading) return;

    setLoading(true);
    setStatusText("");
    setInput("");
    setMessages((current) => [...current, { role: "user", content }]);

    try {
      const response = await fetch(`${apiUrl}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          message: content,
        }),
      });
      if (!response.ok) throw new Error("Backend chưa phản hồi thành công.");

      const data: ChatResponse = await response.json();
      setSessionId(data.session_id);
      setMessages((current) => [...current, { role: "assistant", content: data.answer }]);
      if (data.recommendations?.length) setRecommendations(data.recommendations);
      setSuggestedQuestions(data.suggested_questions?.length ? data.suggested_questions : defaultSuggestedQuestions);
      setTrace(data.react_trace || []);
    } catch (error) {
      const errorMessage =
        error instanceof Error
          ? error.message
          : "Không thể gửi tin nhắn đến backend.";
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: `${errorMessage} Hãy kiểm tra FastAPI ở ${apiUrl}.`,
        },
      ]);
    } finally {
      setLoading(false);
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    sendMessage();
  }

  return (
    <main className="app-shell">
      <header className="topbar">
        <div>
          <h1>AI Food Recommendation Agent</h1>
          <p>Gợi ý món ăn từ dataset JSON local bằng FastAPI + ReAct tools</p>
        </div>
        <button className="secondary-button" onClick={createNewSession} disabled={loading}>
          Tạo chat mới
        </button>
      </header>

      <section className="workspace">
        <div className="chat-panel">
          <div className="panel-heading">
            <h2>Lịch sử chat</h2>
            <span>{sessionId ? `Session ${sessionId.slice(0, 8)}` : "Đang tạo session"}</span>
          </div>

          <div className="quick-prompts" aria-label="Gợi ý nhanh">
            {quickPrompts.map((prompt) => (
              <button
                key={prompt}
                type="button"
                className="chip"
                onClick={() => sendMessage(prompt)}
                disabled={loading}
              >
                {prompt}
              </button>
            ))}
          </div>

          <div className="category-area">
            <div className="category-title">Category</div>
            <div className="category-prompts" aria-label="Danh mục món ăn">
              {categoryPrompts.map((prompt) => (
                <button
                  key={prompt}
                  type="button"
                  className="chip category-chip"
                  onClick={() => sendMessage(`Tôi muốn ${prompt}`)}
                  disabled={loading}
                >
                  {prompt}
                </button>
              ))}
            </div>
          </div>

          <div className="message-list">
            {messages.length === 0 ? (
              <div className="empty-state">
                Nhập yêu cầu hoặc bấm một gợi ý nhanh để bắt đầu demo.
              </div>
            ) : (
              messages.map((message, index) => (
                <article key={`${message.role}-${index}`} className={`message ${message.role}`}>
                  <span>{message.role === "user" ? "Bạn" : "Agent"}</span>
                  <p>{message.content}</p>
                </article>
              ))
            )}
            <div ref={messagesEndRef} />
          </div>

          <form className="input-row" onSubmit={handleSubmit}>
            <input
              value={input}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ví dụ: Gợi ý món chiên xào dưới 60k và giao dưới 25 phút"
              disabled={loading}
            />
            <button type="submit" disabled={loading || !input.trim()}>
              {loading ? "Đang gửi" : "Gửi"}
            </button>
          </form>
          {statusText ? <p className="status-text">{statusText}</p> : null}

          <div className="suggestion-area">
            <div className="suggestion-title">Câu hỏi gợi ý</div>
            <div className="suggestion-prompts" aria-label="Câu hỏi gợi ý tự động">
              {suggestedQuestions.map((question) => (
                <button
                  key={question}
                  type="button"
                  className="chip suggestion-chip"
                  onClick={() => sendMessage(question)}
                  disabled={loading}
                >
                  {question}
                </button>
              ))}
            </div>
          </div>

          <section className="trace-panel">
            <button
              type="button"
              className="trace-toggle"
              onClick={() => setTraceOpen((current) => !current)}
            >
              ReAct Trace
              <span>{traceOpen ? "Ẩn" : "Hiện"}</span>
            </button>
            {traceOpen ? (
              <div className="trace-list">
                {trace.length === 0 ? (
                  <p className="trace-empty">Trace sẽ xuất hiện sau khi agent xử lý tin nhắn.</p>
                ) : (
                  trace.map((step, index) => (
                    <article key={`${step.step}-${index}`} className="trace-step">
                      <strong>{step.step}</strong>
                      {step.tool ? <code>{step.tool}</code> : null}
                      {step.input !== undefined ? (
                        <pre>{traceValue(step.input)}</pre>
                      ) : (
                        <pre>{traceValue(step.content)}</pre>
                      )}
                      {step.input !== undefined && step.content !== undefined ? (
                        <pre>{traceValue(step.content)}</pre>
                      ) : null}
                    </article>
                  ))
                )}
              </div>
            ) : null}
          </section>
        </div>

        <aside className="recommendation-panel">
          <div className="panel-heading">
            <h2>Recommendation cards</h2>
            <span>{recommendations.length ? `${recommendations.length} món` : "Chưa có gợi ý"}</span>
          </div>

          <div className="cards-grid">
            {recommendations.length === 0 ? (
              <div className="empty-card">Các món phù hợp sẽ hiển thị tại đây.</div>
            ) : (
              recommendations.map((item, index) => {
                const imageUrl = item.image_urls?.[0];
                const hasUrl = Boolean(item.url);
                const estimatedTime = getEstimatedTime(item);
                return (
                  <article key={`${item.name}-${index}`} className="food-card">
                    {imageUrl ? (
                      <img src={imageUrl} alt={item.name} className="food-image" />
                    ) : (
                      <div className="image-placeholder">Không có ảnh</div>
                    )}
                    <div className="food-content">
                      <div>
                        <h3>{item.name}</h3>
                        <p className="muted">{item.brand || "Chưa rõ quán/brand"}</p>
                      </div>
                      <div className="meta-grid">
                        <span>{formatCategory(item.category)}</span>
                        <span>Rating {item.rating || 0}</span>
                        <span>Giá gốc {formatOriginalPrice(item.price)}</span>
                        <span>Voucher {item.voucher || 0}%</span>
                        <span>Giá mới {formatVnd(item.new_price)}</span>
                        <span>{estimatedTime} phút</span>
                        <span>{item.sold_count || 0} lượt bán</span>
                      </div>
                      <p className="reason">{item.reason}</p>
                      <div className="card-actions">
                        <button type="button" onClick={() => sendMessage(`giới thiệu món số ${index + 1}`)}>
                          Xem chi tiết
                        </button>
                        <button
                          type="button"
                          className="link-button"
                          disabled={!hasUrl}
                          onClick={() => {
                            if (item.url) window.open(item.url, "_blank");
                          }}
                        >
                          {hasUrl ? "Mở link món ăn" : "Chưa có link món ăn"}
                        </button>
                      </div>
                    </div>
                  </article>
                );
              })
            )}
          </div>
        </aside>
      </section>
    </main>
  );
}
