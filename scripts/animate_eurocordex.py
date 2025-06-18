from pathlib import Path

import imageio
import matplotlib.pyplot as plt

from ccee.cordex import load_eurocordex_data, plot_eurocordex_data


def main(fout: str = "output"):
    # Load the Euro-CORDEX data
    ds = load_eurocordex_data()

    ls_files = []

    # Plot the Euro-CORDEX data
    for year in range(2021, 2031):
        for month in range(1, 13):
            # Create a date string for the tenth day of the month
            # (easier to break ties when the reference is the middle of the month)
            date = f"{year}-{month:02d}-10"
            fig, ax = plot_eurocordex_data(ds, date=date)
            # Make sure the output directory exists
            folder = Path(fout)
            folder.mkdir(parents=True, exist_ok=True)
            # Use the plot title as the filename
            title = ax.get_title()
            # Extract the text between parentheses
            title = title.split("(")[-1].split(")")[0]
            # Save the figure as a JPEG file
            file = folder / f"tas_{title}.JPEG"
            plt.savefig(file, dpi=300)
            plt.close()
            ls_files.append(file)

    # Sort the files by date
    ls_files = sorted(list(set(ls_files)))

    # Create a gif from the png files
    with imageio.get_writer("output/tas.gif", mode="I", loop=0) as writer:
        for filename in ls_files:
            image = imageio.imread(filename)
            writer.append_data(image)
    # Remove the png files
    for filename in ls_files:
        filename.unlink()


if __name__ == "__main__":
    main()
