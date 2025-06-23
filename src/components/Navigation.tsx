import { Menu } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "./ui/button";
import { DropdownNavigation } from "./ui/dropdown-navigation";
import { Sheet, SheetContent, SheetTrigger } from "./ui/sheet";

const Navigation = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 50);
    };

    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const menuItems = [
    { id: 1, label: "Overview", link: "/overview" },
    { id: 2, label: "Use Cases", link: "/use-cases" },
    { id: 3, label: "Architecture", link: "/architecture" },
    { id: 4, label: "Demos", link: "/demos" },
    { id: 5, label: "Pricing", link: "/pricing" },

    { id: 7, label: "Dashboard", link: "/try-dashboard" },
  ];

  const mobileNavItems = [
    { name: "Overview", href: "/overview", isLink: true },
    { name: "Use Cases", href: "/use-cases", isLink: true },
    { name: "Architecture", href: "/architecture", isLink: true },
    { name: "Demos", href: "/demos", isLink: true },
    { name: "Pricing", href: "/pricing", isLink: true },

    { name: "Dashboard", href: "/try-dashboard", isLink: true },
  ];

  return (
    <header
      className={`fixed top-3.5 left-1/2 -translate-x-1/2 z-50 transition-all duration-300 rounded-full ${
        isScrolled
          ? "h-14 bg-[#1B1B1B]/40 backdrop-blur-xl border border-white/10 scale-95 w-[92%] max-w-5xl"
          : "h-14 bg-[#1B1B1B] w-[96%] max-w-6xl"
      }`}
    >
      <div className="mx-auto h-full px-4">
        <nav className="flex items-center justify-between h-full">
          <Link to="/" className="flex items-center gap-2">
            <span className="font-bold text-base">Haven Health Passport</span>
          </Link>

          {/* Desktop Navigation */}
          <div className="hidden md:flex items-center">
            <DropdownNavigation navItems={menuItems} />
          </div>

          <div className="hidden md:flex items-center">
            <Link to="/about-me">
              <Button size="sm" className="button-gradient">
                About the Dev
              </Button>
            </Link>
          </div>

          {/* Mobile Navigation */}
          <div className="md:hidden">
            <Sheet open={isMobileMenuOpen} onOpenChange={setIsMobileMenuOpen}>
              <SheetTrigger asChild>
                <Button variant="outline" size="icon" className="glass">
                  <Menu className="h-5 w-5" />
                </Button>
              </SheetTrigger>
              <SheetContent className="bg-[#1B1B1B]">
                <div className="flex flex-col gap-4 mt-8">
                  {mobileNavItems.map((item) => (
                    <Link
                      key={item.name}
                      to={item.href}
                      className="text-lg text-muted-foreground hover:text-foreground transition-colors"
                      onClick={() => setIsMobileMenuOpen(false)}
                    >
                      {item.name}
                    </Link>
                  ))}
                  <Link to="/about-me">
                    <Button
                      onClick={() => setIsMobileMenuOpen(false)}
                      className="button-gradient mt-4"
                    >
                      About the Dev
                    </Button>
                  </Link>
                </div>
              </SheetContent>
            </Sheet>
          </div>
        </nav>
      </div>
    </header>
  );
};

export default Navigation;
