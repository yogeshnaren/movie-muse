
URL = "https://imsdb.com/all-scripts.html"

def download_movie_scripts(url, save_path):
    """
    Function to download the movie scripts from specified website URL and save to local folder.

    Args:

    """
    import requests
    import html2text
    from tqdm import tqdm
    from bs4 import BeautifulSoup

    response = requests.get(url)
    content = response.content

    soup = BeautifulSoup(content, "html.parser")
    links = soup.find_all("a")

    movie_names_list = []
    error_list = []

    # Extract all the the links that have script in the html page
    raw_movie_links = [link.get("href") for link in links if "script" in str(link).lower()]

    # Split the movie names from the movie links
    raw_movie_links = [link.split('/')[-1].replace(".html", "") for link in raw_movie_links]

    for name in raw_movie_links:
        if "script" in name.lower():
            name = name.replace(" Script", "")
            name = name.replace(", The", "")
            name = name.replace(' ','-')
            movie_names_list.append(name)

    # Create link from movie name and imsdb link
    if "imsdb" in url.lower():
        movie_links = [f"https://imsdb.com/scripts/{name}.html" for name in movie_names_list]

    for index in tqdm(range(len(movie_links)), desc="Movie Script Download From IMSDB"):
        url = movie_links[index]
        # Send a request to the URL and get the page content
        response = requests.get(url)
        html = response.content

        # Parse the HTML page using Beautiful Soup
        soup = BeautifulSoup(html, 'html.parser')

        # Find the <title> tag that contains the movie script
        pre_tag = soup.find('pre')
        # movie_names_list[index].upper().replace('-', ' ')

        try:
            # Extract the movie script from the <pre> tag
            movie_script = pre_tag.prettify()
        except:
            error_list.append(movie_names_list[index])
            continue

        # # Extract the movie script from the <script> tag
        # movie_script = script_tag.string

        # Convert the movie script to formatted text using html2text
        html_converter = html2text.HTML2Text()
        html_converter.ignore_links = True
        formatted_text = html_converter.handle(movie_script)

        # Save the movie script as a text file while preserving the formatting
        with open(f'./movie_script_files/{movie_names_list[index].lower()}.txt', 'w') as f:
            f.write(formatted_text)

    print(f"All the following movie scripts are not downloaded due to error:\n {error_list}")

if __name__ == "__main__":
    download_movie_scripts(url=URL, save_path='.')