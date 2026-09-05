"use client";

import { Mic } from "lucide-react";
import { ScalesIcon } from "@/components/ui";

function renderInline(text: string, keyBase: string) {
  return text.split(/\*\*([^*]+)\*\*/g).map((part, i) =>
    i % 2 === 1 ? (
      <strong key={`${keyBase}-${i}`} className="font-semibold text-ink">
        {part}
      </strong>
    ) : (
      part
    ),
  );
}

function Markdown({ text }: { text: string }) {
  const blocks: React.ReactNode[] = [];
  let bullets: string[] = [];

  const flushBullets = () => {
    if (!bullets.length) return;
    blocks.push(
      <ul key={`ul-${blocks.length}`} className="ml-4 list-disc space-y-1 text-ink/85">
        {bullets.map((b, i) => (
          <li key={i}>{renderInline(b, `li-${blocks.length}-${i}`)}</li>
        ))}
      </ul>,
    );
    bullets = [];
  };

  for (const raw of text.split(/\r?\n/)) {
    const line = raw.trim();
    if (!line) {
      flushBullets();
      continue;
    }

    const heading = line.match(/^(?:#{1,4}\s+(.+)|\*\*([^*]+)\*\*:?$)/);
    if (heading) {
      flushBullets();
      blocks.push(
        <h4
          key={`h-${blocks.length}`}
          className="pt-1 font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-ink/55"
        >
          {heading[1] || heading[2]}
        </h4>,
      );
      continue;
    }

    const bullet = line.match(/^[*\-•]\s+(.+)/);
    if (bullet) {
      bullets.push(bullet[1]);
      continue;
    }

    flushBullets();
    blocks.push(
      <p key={`p-${blocks.length}`} className="text-ink/85">
        {renderInline(line, `p-${blocks.length}`)}
      </p>,
    );
  }
  flushBullets();

  return <div className="space-y-2 text-sm leading-relaxed">{blocks}</div>;
}

export function VoiceSummary({
  content,
  citations,
  onFullAssessment,
}: {
  content: string;
  citations: string[];

  onFullAssessment?: () => void;
}) {
  return (
    <div className="flex justify-start">
      <div className="max-w-[92%] space-y-3">
        <div className="rounded border-2 border-ink bg-surface/65 px-4 py-3 backdrop-blur-md">
          <div className="mb-2 inline-flex items-center gap-1.5 rounded border-2 border-gold-500/50 bg-gold-400/15 px-2 py-0.5 font-mono text-[10px] font-semibold uppercase tracking-[0.1em] text-gold-700">
            <Mic className="h-3 w-3" strokeWidth={2} aria-hidden /> Voice call summary
          </div>
          <Markdown text={content} />
        </div>

        {citations.length > 0 && (
          <div className="rounded border-2 border-ink bg-surface/45 px-4 py-3 backdrop-blur-md">
            <div className="flex items-center gap-2 font-mono text-[11px] font-semibold uppercase tracking-[0.12em] text-ink/55">
              <ScalesIcon className="h-4 w-4 text-gold-600" /> Cases this call relied on
            </div>
            <div className="mt-2.5 space-y-1.5">
              {citations.map((c, i) => (
                <p key={i} className="text-sm leading-relaxed text-ink/75">
                  {c}
                </p>
              ))}
            </div>
          </div>
        )}

        {onFullAssessment && (
          <button
            onClick={onFullAssessment}
            className="flex w-full items-center gap-3 rounded border-2 border-gold-500/60 bg-gold-400/[0.08] px-4 py-3 text-left transition hover:-translate-x-[1px] hover:-translate-y-[1px] hover:shadow-brutal-gold"
          >
            <ScalesIcon className="h-4 w-4 shrink-0 text-gold-600" />
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-ink">Run a full assessment</span>
              <span className="mt-0.5 block text-xs text-ink/60">
                Win/lose estimate, the factors for and against, and the precedents behind it,
                using everything from this call.
              </span>
            </span>
          </button>
        )}
      </div>
    </div>
  );
}
