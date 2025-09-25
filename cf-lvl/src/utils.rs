use reqwest::blocking::Client;
use serde::de::DeserializeOwned;
use std::error::Error;

pub fn build_client() -> Result<Client, Box<dyn Error>> {
    let mut headers = reqwest::header::HeaderMap::new();
    headers.insert(
        reqwest::header::USER_AGENT,
        reqwest::header::HeaderValue::from_static(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Safari/537.36 cf-lvl/0.3",
        ),
    );
    headers.insert(
        reqwest::header::ACCEPT,
        reqwest::header::HeaderValue::from_static("application/json, text/plain, */*"),
    );
    headers.insert(
        reqwest::header::ACCEPT_LANGUAGE,
        reqwest::header::HeaderValue::from_static("en-US,en;q=0.9"),
    );
    headers.insert(
        reqwest::header::REFERER,
        reqwest::header::HeaderValue::from_static("https://kenkoooo.com/atcoder/"),
    );

    Ok(Client::builder().default_headers(headers).build()?)
}

pub fn fetch_json<T>(client: &Client, url: &str, label: &str) -> Result<Vec<T>, Box<dyn Error>>
where
    T: DeserializeOwned,
{
    let response = client.get(url).send()?;
    parse_json_payload(response, label)
}

pub fn parse_json_payload<T>(
    response: reqwest::blocking::Response,
    label: &str,
) -> Result<Vec<T>, Box<dyn Error>>
where
    T: DeserializeOwned,
{
    let status = response.status();
    let text = response.text()?;

    if !status.is_success() {
        let snippet: String = text.chars().take(200).collect();
        return Err(format!(
            "Failed to fetch {}: HTTP {}. Response starts with: {}",
            label, status, snippet
        )
        .into());
    }

    let value: serde_json::Value = serde_json::from_str(&text).map_err(|err| {
        let snippet: String = text.chars().take(200).collect();
        format!(
            "Failed to parse {} as JSON: {}. Response starts with: {}",
            label, err, snippet
        )
    })?;

    let items = match value {
        serde_json::Value::Array(array) => array,
        serde_json::Value::Object(map) => map.into_iter().map(|(_, v)| v).collect(),
        _ => {
            return Err(format!(
                "Unexpected JSON payload for {}: expected array or object",
                label
            )
            .into())
        }
    };

    items
        .into_iter()
        .map(serde_json::from_value)
        .collect::<Result<Vec<T>, _>>()
        .map_err(|err| err.into())
}
