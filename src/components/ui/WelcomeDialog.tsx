import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ExternalLink, Github } from "lucide-react";
import { useRef, useState } from "react";

interface WelcomeDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function WelcomeDialog({ open, onOpenChange }: WelcomeDialogProps) {
  const [hasReadToBottom, setHasReadToBottom] = useState(false);
  const contentRef = useRef<HTMLDivElement>(null);

  const handleScroll = () => {
    const content = contentRef.current;
    if (!content) return;

    const scrollPercentage =
      content.scrollTop / (content.scrollHeight - content.clientHeight);
    if (scrollPercentage >= 0.99 && !hasReadToBottom) {
      setHasReadToBottom(true);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex flex-col gap-0 p-0 sm:max-h-[min(640px,80vh)] sm:max-w-lg [&>button:last-child]:top-3.5">
        <DialogHeader className="contents space-y-0 text-left">
          <DialogTitle className="border-b border-border px-6 py-4 text-base">
            Welcome to the Haven Health Passport Demo
          </DialogTitle>
          <div ref={contentRef} onScroll={handleScroll} className="overflow-y-auto">
            <DialogDescription asChild>
              <div className="px-6 py-4">
                <div className="space-y-4 [&_strong]:font-semibold [&_strong]:text-foreground">
                  <div className="space-y-4">
                    <div className="space-y-1">
                      <p>
                        <strong>AWS Breaking Barriers Hackathon Demo</strong>
                      </p>
                      <p>
                        This is a demo project created for the Amazon Web Services (AWS)
                        Breaking Barriers Hackathon. Haven Health Passport is a concept
                        application designed to revolutionize healthcare access for
                        displaced populations worldwide.
                      </p>
                    </div>

                    <div className="space-y-1">
                      <p>
                        <strong>About This Demo</strong>
                      </p>
                      <p>
                        Haven Health Passport is a blockchain-verified health record
                        system built for the AWS Breaking Barriers Hackathon. This
                        demonstration showcases how AWS services can be leveraged to
                        create secure, portable, and accessible health records for the
                        100+ million displaced people globally.
                      </p>
                    </div>

                    <div className="space-y-1">
                      <p>
                        <strong>Built With AWS Services</strong>
                      </p>
                      <ul className="list-disc pl-6 space-y-1">
                        <li>Amazon Transcribe Medical – voice-to-text triage</li>
                        <li>AWS Textract – document digitisation</li>
                        <li>Amazon Polly – multilingual text-to-speech</li>
                        <li>AWS HealthLake – FHIR-compliant data store</li>
                        <li>AWS Managed Blockchain for tamper-proof records</li>
                        <li>Amazon Bedrock for AI-powered medical translation</li>
                        <li>AWS Comprehend Medical for health data processing</li>
                      </ul>
                    </div>

                    <div className="space-y-1">
                      <p>
                        <strong>Open Source & Community</strong>
                      </p>
                      <p>You are welcome to:</p>
                      <ul className="list-disc pl-6 space-y-1">
                        <li>⭐ Star or watch the repo</li>
                        <li>
                          🍴 Fork the code for learning and non-commercial prototypes
                        </li>
                        <li>🛠️ Open issues or PRs to improve features</li>
                        <li>
                          💡 Reuse the architecture for humanitarian-tech inspiration
                        </li>
                      </ul>
                      <p className="mt-2">
                        <strong>Licence</strong> — Released under Apache 2.0.
                        <br />
                        Attribution is required, and resubmitting this project to
                        hackathons, grant programs, or investment funds without
                        permission is strictly prohibited.
                      </p>
                    </div>

                    <div className="space-y-1">
                      <p>
                        <strong>
                          AWS Breaking Barriers Challenge - Eligibility Confirmation
                        </strong>
                      </p>
                      <p>
                        <strong>
                          This project is eligible for the AWS Breaking Barriers
                          Challenge.
                        </strong>
                        <br />
                        Haven Health Passport was developed independently without any
                        financial or preferential support from AWS or Amazon. This
                        project has received NO funding, investment, contracts, or
                        commercial licenses from AWS/Amazon prior to or during the
                        hackathon submission period.
                      </p>
                      <p>
                        <strong>Future Funding Timeline:</strong>
                        <br />
                        Only AFTER the AWS judging period concludes will this project be
                        considered for submission to crypto-impact funds, grant
                        programs, or other funding opportunities. Any future funding
                        applications will occur post-judging and do not create conflicts
                        with the AWS Breaking Barriers Challenge eligibility
                        requirements.
                      </p>
                    </div>

                    <div className="space-y-1">
                      <p>
                        <strong>Mission & Impact</strong>
                      </p>
                      <p>
                        Crossing borders shouldn&apos;t erase a person&apos;s medical
                        history. Haven Health Passport shows how cloud and blockchain
                        technologies can preserve health records for displaced
                        populations worldwide.
                      </p>
                    </div>

                    <div className="space-y-1">
                      <p>
                        <strong>Collaboration Opportunities</strong>
                      </p>
                      <p>
                        If you are part of an NGO, healthcare organization, or
                        non-profit interested in developing this project further, feel
                        free to reach out for collaboration opportunities.
                      </p>
                    </div>

                    <div className="space-y-1">
                      <p>
                        <strong>Disclaimer</strong>
                      </p>
                      <p>
                        All data shown here is simulated. Do not use this application
                        for real patient records or clinical decisions.
                        <br />
                        Always seek qualified medical advice.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </DialogDescription>
          </div>
        </DialogHeader>
        <DialogFooter className="border-t border-border px-6 py-4 sm:items-center">
          {!hasReadToBottom && (
            <span className="grow text-xs text-muted-foreground max-sm:text-center">
              Please review this notice before proceeding.
            </span>
          )}
          <DialogClose asChild>
            <Button
              type="button"
              variant="outline"
              onClick={() =>
                window.open("https://github.com/cdgtlmda/havenhealthpassport", "_blank")
              }
            >
              <Github className="w-4 h-4 mr-2" />
              View on GitHub
            </Button>
          </DialogClose>
          <DialogClose asChild>
            <Button type="button" disabled={!hasReadToBottom}>
              <ExternalLink className="w-4 h-4 mr-2" />
              Explore Demo
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export { WelcomeDialog };
