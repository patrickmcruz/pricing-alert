import re

with open("data/mercadolivre.html", "r", encoding="utf-8") as f:
    html = f.read()

# Find all occurrences of andes-money-amount
matches = re.findall(r'<span class="andes-money-amount[^>]*>.*?<span class="andes-money-amount__fraction">([^<]+)</span>', html)
print("Money amount fractions found:", matches)

# Find ui-pdp-price__second-line block
m = re.search(r'<div class="ui-pdp-price__second-line">(.*?)</div>', html, re.DOTALL)
if m:
    print("Found second-line price block")
    fraction = re.search(r'<span class="andes-money-amount__fraction">([^<]+)</span>', m.group(1))
    cents = re.search(r'<span class="andes-money-amount__cents[^>]*>([^<]+)</span>', m.group(1))
    if fraction:
        price = fraction.group(1)
        if cents:
            price += "." + cents.group(1)
        print("Main price extracted:", price)

# Find installments
m2 = re.search(r'em.*?<span class="andes-money-amount__fraction">([^<]+)</span>', html, re.IGNORECASE)
if m2:
    print("Found installment fraction:", m2.group(1))
    
# Find all "em Xx" texts
em_matches = re.findall(r'em.*?(\d+)x', html, re.IGNORECASE)
print("Installment counts found:", em_matches)
    
if installments_container:
    print("Found installments container:", installments_container.text.strip())
else:
    # Let's search for "x" or "sem juros"
    for el in soup.find_all(string=lambda t: "sem juros" in str(t).lower() or "x " in str(t).lower()):
        parent = el.parent
        print("Possible installment text:", parent.text.strip())

# Another check for the main price block
for el in soup.select('.andes-money-amount'):
    print("andes-money-amount:", el.text.strip())

