import requests
from time import sleep
from pprint import pprint

# List of test cases
tests = [
    "test1",
    "test2",
    "test3",
    "test4",
    "test5",
]

# API details
API_URL = "http://127.0.0.1:5000"
REPO_URL = "https://github.com/krosspile/test_repo.git"

# Session for HTTP requests
session = requests.Session()

def send_analysis_task(entrypoint: str):
    """
    Send an analysis task to the server.
    Args:
        entrypoint (str): Name of the test entrypoint.
    Returns:
        str: Job ID if task submission is successful, otherwise None.
    """
    print(f"[*] Sending analysis task: {entrypoint}")
    try:
        response = session.post(
            f"{API_URL}/analyze",
            data={
                "entrypoint": f"{entrypoint}/main.c",
                "repository": REPO_URL,
            },
        )
        response.raise_for_status()
        return response.text.split("Job: ")[-1]
    except requests.RequestException as e:
        print(f"[!] Failed to send task for {entrypoint}: {e}")
        return None

def download_job_result(job_id: str):
    """
    Poll the server until the job is completed, then fetch the results.
    Args:
        job_id (str): Job ID of the submitted analysis task.
    """
    if not job_id:
        print("[!] Invalid job ID. Skipping...")
        return

    print(f"[*] Downloading job[{job_id}] result")
    while True:
        try:
            response = session.post(
                f"{API_URL}/patchs",
                data={"id": job_id, "only_bug_changelog": True},
            )

            if response.text == "201":
                print(f"[!] No vulnerabilities found for job {job_id}")
                return
            elif response.text == "404":
                print(f"[!] Repo not found for job {job_id}")
                return
            elif response.status_code == 200:
                print(f"[+] Job {job_id} completed successfully:")
                data = response.json()
                for d in data:
                    pprint(d)
                break
        except requests.RequestException as e:
            print(f"[!] Error downloading result for job {job_id}: {e}")
            return

        sleep(5)

def main():
    """
    Main function to send tasks and fetch their results.
    """
    for test in tests:
        job_id = send_analysis_task(test)
        if job_id:
            sleep(10)  # Delay before checking the result
            download_job_result(job_id)

if __name__ == "__main__":
    main()
