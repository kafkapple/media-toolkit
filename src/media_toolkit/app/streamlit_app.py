"""Streamlit UI for general-purpose media downloading."""

import os
import streamlit as st

from media_toolkit.extractor import extract_media
from media_toolkit.downloader.general_downloader import DownloadManager


def main():
    st.set_page_config(page_title="Media Toolkit - Downloader", layout="wide")

    st.title("Media Toolkit - Downloader")

    # Sidebar for configuration
    with st.sidebar:
        st.header("Settings")
        save_dir = st.text_input("Download Directory", value=os.path.expanduser("~/Downloads/MediaDownloader"))

        st.divider()
        st.subheader("Filters")
        filter_type = st.multiselect("Show Media Types", ["video", "image"], default=["video", "image"])

        st.divider()
        st.subheader("Advanced/Security")
        st.caption("Use if bot protection blocks access.")
        cookies_browser = st.selectbox(
            "Use Cookies from Browser (for Video)",
            options=[None, "chrome", "firefox", "safari", "edge", "opera", "vivaldi", "brave"],
            help="Requires the browser to be closed (except Chrome/Edge often work open). Helps with age-gated or login-wall content."
        )

    # Main Input
    url = st.text_input("Enter URL to analyze:")

    if "media_items" not in st.session_state:
        st.session_state.media_items = []
    if "selected_indices" not in st.session_state:
        st.session_state.selected_indices = set()

    if st.button("Analyze"):
        if url:
            with st.spinner("Extracting media..."):
                items, logs = extract_media(url, cookies_browser=cookies_browser)
                if items:
                    st.session_state.media_items = items
                    st.session_state.selected_indices = set(range(len(items))) # Select all by default
                    st.success(f"Found {len(items)} items!")
                else:
                    st.error("No media found or URL not supported.")
                    if logs:
                        with st.expander("See detailed errors"):
                            for log in logs:
                                st.write(log)
                            st.info("Try checking the URL or ensure it is a supported video platform / accessible website.")
        else:
            st.warning("Please enter a URL.")

    # Display Results
    if st.session_state.media_items:
        st.divider()
        st.subheader("Found Media")

        # Filter items based on user selection
        filtered_items = [item for item in st.session_state.media_items if item.type in filter_type]

        if not filtered_items:
            st.info(f"No items found matching the selected filters ({', '.join(filter_type)}).")
        else:
            # Select All / Deselect All (targeting only filtered items)
            col1, col2 = st.columns(2)
            # Map filtered items back to their original indices
            filtered_indices = [i for i, item in enumerate(st.session_state.media_items) if item.type in filter_type]

            if col1.button("Select All Visible"):
                st.session_state.selected_indices.update(filtered_indices)
            if col2.button("Deselect All Visible"):
                st.session_state.selected_indices.difference_update(filtered_indices)

            # Grid view
            cols = st.columns(4)
            for idx, item_idx in enumerate(filtered_indices):
                item = st.session_state.media_items[item_idx]
                col = cols[idx % 4]
                with col:
                    # Show thumbnail
                    if item.thumbnail_url:
                        try:
                            st.image(item.thumbnail_url)
                        except Exception:
                            st.text("No Preview")
                    else:
                        st.text("No Preview")

                    # Checkbox
                    is_selected = item_idx in st.session_state.selected_indices
                    checked = st.checkbox(f"{item.title or 'Unknown'} ({item.type})", value=is_selected, key=f"check_{item_idx}")

                    if checked:
                        st.session_state.selected_indices.add(item_idx)
                    elif item_idx in st.session_state.selected_indices:
                        st.session_state.selected_indices.remove(item_idx)

                    st.caption(f"Size: {item.file_size or 'Unknown'}")

        st.divider()

        if st.button("Download Selected"):
            selected_items = [st.session_state.media_items[i] for i in st.session_state.selected_indices]
            if selected_items:
                manager = DownloadManager(save_dir, cookies_browser=cookies_browser)
                progress_bar = st.progress(0)
                status_text = st.empty()

                total = len(selected_items)
                for i, item in enumerate(selected_items):
                    status_text.text(f"Downloading {i+1}/{total}: {item.title}")
                    manager.download_items([item]) # Download one by one to update UI
                    progress_bar.progress((i + 1) / total)

                st.success(f"Downloaded {len(selected_items)} files to {save_dir}")
                status_text.text("Done!")
            else:
                st.warning("No items selected.")


if __name__ == "__main__":
    main()
