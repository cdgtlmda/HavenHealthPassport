import { Github, Mail, Youtube } from "lucide-react";
import { Link } from "react-router-dom";
import { Button } from "./ui/button";

const Footer = () => {
  return (
    <footer className="w-full py-12 mt-20">
      <div className="container px-4">
        <div className="bg-gradient-to-r from-primary to-[#9fa0f7] rounded-xl p-8 md:p-12">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 md:gap-12">
            <div className="space-y-4 md:col-span-1">
              <h3 className="font-medium text-lg text-white">Haven Health Passport</h3>
              <p className="text-sm text-white/80 max-w-sm">
                Blockchain-verified health records for displaced populations worldwide.
              </p>
              <div className="flex space-x-3 pt-2">
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-white hover:bg-white/20 w-9 h-9"
                  asChild
                >
                  <a
                    href="https://github.com/cdgtlmda/havenhealthpassport"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Github className="w-4 h-4" />
                  </a>
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-white hover:bg-white/20 w-9 h-9"
                  asChild
                >
                  <a
                    href="https://substack.com/@cdgtlmda"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <img
                      src="/Substack.svg"
                      alt="Substack"
                      className="w-4 h-4 brightness-0 invert"
                    />
                  </a>
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-white hover:bg-white/20 w-9 h-9"
                  asChild
                >
                  <a
                    href="https://youtube.com/@cdgtlmda"
                    target="_blank"
                    rel="noopener noreferrer"
                  >
                    <Youtube className="w-4 h-4" />
                  </a>
                </Button>
                <Button
                  variant="ghost"
                  size="icon"
                  className="text-white hover:bg-white/20 w-9 h-9"
                  asChild
                >
                  <a href="mailto:cdgtlmda@pm.me">
                    <Mail className="w-4 h-4" />
                  </a>
                </Button>
              </div>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-white mb-3">Platform</h3>
              <ul className="space-y-2">
                <li>
                  <Link
                    to="/overview"
                    className="text-sm text-white/80 hover:text-white transition-colors"
                  >
                    Overview
                  </Link>
                </li>
                <li>
                  <Link
                    to="/demos"
                    className="text-sm text-white/80 hover:text-white transition-colors"
                  >
                    Demos
                  </Link>
                </li>
                <li>
                  <Link
                    to="/try-dashboard"
                    className="text-sm text-white/80 hover:text-white transition-colors"
                  >
                    Dashboard
                  </Link>
                </li>
              </ul>
            </div>

            <div>
              <h3 className="text-sm font-semibold text-white mb-3">Resources</h3>
              <ul className="space-y-2">
                <li>
                  <Link
                    to="/architecture"
                    className="text-sm text-white/80 hover:text-white transition-colors"
                  >
                    Architecture
                  </Link>
                </li>
                <li>
                  <Link
                    to="/use-cases"
                    className="text-sm text-white/80 hover:text-white transition-colors"
                  >
                    Use Cases
                  </Link>
                </li>
                <li></li>
                <li>
                  <Link
                    to="/about-me"
                    className="text-sm text-white/80 hover:text-white transition-colors"
                  >
                    About Me
                  </Link>
                </li>
              </ul>
            </div>
          </div>

          <div className="mt-12 pt-8 border-t border-white/20">
            <p className="text-sm text-white/80 text-center">
              © {new Date().getFullYear()} Haven Health Passport. All rights reserved.
            </p>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
